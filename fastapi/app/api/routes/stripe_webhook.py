from __future__ import annotations

import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db
from app.core.config import settings
from app.core.critical_logging import log_critical_event
from app.models.order import Order
from app.models.enums import OrderStatus
from app.services.email import send_admin_order_email, send_customer_order_email
from app.services.payment_diagnostics import (
    build_stripe_payment_intent_failure_diagnostics,
    build_stripe_session_failure_diagnostics,
    payment_failure_values,
    payment_success_values,
)
from app.services.payment_events import record_payment_event_best_effort
from app.services.orders import resolve_order_status_from_session
from app.services.webhook_events import (
    is_webhook_event_processed,
    mark_webhook_event_processed,
)

router = APIRouter(prefix="/api/stripe", tags=["stripe"])
MAX_WEBHOOK_BODY_BYTES = 1_000_000


def _load_order_for_session(
    db: Session, order_id: str | None, session_id: str | None
) -> Order | None:
    if order_id:
        order = (
            db.execute(
                select(Order).where(Order.id == order_id).options(joinedload(Order.items))
            )
            .unique()
            .scalars()
            .first()
        )
        if order:
            return order

    if session_id:
        return (
            db.execute(
                select(Order)
                .where(Order.stripe_session_id == session_id)
                .options(joinedload(Order.items))
            )
            .unique()
            .scalars()
            .first()
        )

    return None


def _can_record_payment_failure(order: Order) -> bool:
    return order.status == OrderStatus.PENDING


def _read_provider_attr(obj: object, key: str) -> object:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _provider_id(value: object) -> str | None:
    if not value:
        return None
    if isinstance(value, str):
        return value
    nested_id = _read_provider_attr(value, "id")
    return str(nested_id) if nested_id else None


def _stripe_session_context(session: object, *, event_type: str) -> dict[str, object]:
    return {
        "stripe_event_type": event_type,
        "session_status": _read_provider_attr(session, "status"),
        "payment_status": _read_provider_attr(session, "payment_status"),
        "amount_total": _read_provider_attr(session, "amount_total"),
        "currency": _read_provider_attr(session, "currency"),
        "created": _read_provider_attr(session, "created"),
        "expires_at": _read_provider_attr(session, "expires_at"),
    }


def _stripe_payment_intent_context(
    payment_intent: object, *, event_type: str
) -> dict[str, object]:
    last_error = _read_provider_attr(payment_intent, "last_payment_error")
    return {
        "stripe_event_type": event_type,
        "intent_status": _read_provider_attr(payment_intent, "status"),
        "amount": _read_provider_attr(payment_intent, "amount"),
        "currency": _read_provider_attr(payment_intent, "currency"),
        "error_code": _read_provider_attr(last_error, "code"),
        "decline_code": _read_provider_attr(last_error, "decline_code"),
        "error_type": _read_provider_attr(last_error, "type"),
        "provider_message": _read_provider_attr(last_error, "message"),
    }


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    if not settings.stripe_secret_key or not settings.stripe_webhook_secret:
        log_critical_event(
            domain="payment",
            event="stripe_webhook_not_configured",
            message="Stripe webhook called while Stripe webhook settings are missing.",
            request=request,
        )
        raise HTTPException(status_code=400, detail="Stripe webhook is not configured.")

    signature = request.headers.get("stripe-signature")
    if not signature:
        log_critical_event(
            domain="payment",
            event="stripe_signature_missing",
            message="Stripe webhook rejected: missing signature header.",
            request=request,
            level=logging.WARNING,
        )
        raise HTTPException(status_code=400, detail="Missing Stripe signature.")

    raw_content_length = request.headers.get("content-length")
    if raw_content_length and raw_content_length.isdigit() and int(raw_content_length) > MAX_WEBHOOK_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Webhook payload is too large.")
    payload = await request.body()
    if len(payload) > MAX_WEBHOOK_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Webhook payload is too large.")
    stripe.api_key = settings.stripe_secret_key

    try:
        event = stripe.Webhook.construct_event(
            payload=payload, sig_header=signature, secret=settings.stripe_webhook_secret
        )
    except Exception:
        log_critical_event(
            domain="payment",
            event="stripe_signature_invalid",
            message="Stripe webhook rejected: invalid signature.",
            request=request,
            level=logging.WARNING,
        )
        raise HTTPException(status_code=400, detail="Invalid signature.")

    event_livemode = event.get("livemode")
    if isinstance(event_livemode, bool):
        expected_livemode = settings.stripe_secret_key.startswith("sk_live_")
        if event_livemode != expected_livemode:
            log_critical_event(
                domain="payment",
                event="stripe_webhook_livemode_mismatch",
                message="Stripe webhook mode does not match the configured secret key.",
                request=request,
                context={"event_livemode": event_livemode},
                level=logging.WARNING,
            )
            raise HTTPException(status_code=400, detail="Invalid Stripe event.")

    event_id = event.get("id")
    if not isinstance(event_id, str) or not event_id.strip():
        log_critical_event(
            domain="payment",
            event="stripe_event_missing_id",
            message="Stripe webhook rejected: missing event id.",
            request=request,
            level=logging.WARNING,
        )
        raise HTTPException(status_code=400, detail="Invalid Stripe event.")

    if is_webhook_event_processed(db, provider="stripe", event_id=event_id):
        return {"received": True}

    event_type = str(event.get("type") or "")

    if event_type in ["checkout.session.completed", "checkout.session.async_payment_succeeded"]:
        session = event["data"]["object"]
        metadata = session.get("metadata") or {}
        order_id = metadata.get("orderId")
        session_id = session.get("id")
        payment_intent_id = _provider_id(session.get("payment_intent"))
        order = _load_order_for_session(db, order_id=order_id, session_id=session_id)

        if not order:
            log_critical_event(
                domain="payment",
                event="webhook_order_not_found",
                message="Stripe webhook references unknown order.",
                request=request,
                context={"order_id": order_id, "stripe_session_id": session_id},
            )
        elif not isinstance(session_id, str) or order.stripe_session_id != session_id:
            log_critical_event(
                domain="payment",
                event="stripe_session_id_mismatch",
                message="Stripe webhook session id does not match stored order session id.",
                request=request,
                context={
                    "order_id": order.id,
                    "stripe_session_id": session_id,
                    "expected_stripe_session_id": order.stripe_session_id,
                },
            )
        else:
            record_payment_event_best_effort(
                db,
                order_id=order.id,
                event="stripe_webhook_received",
                provider="stripe",
                source="stripe_webhook",
                message=f"Stripe webhook received: {event_type}.",
                stripe_session_id=session_id,
                stripe_event_id=event_id,
                payment_intent_id=payment_intent_id,
                context=_stripe_session_context(session, event_type=event_type),
                request=request,
            )
            resolved_status = resolve_order_status_from_session(order, session)
            if resolved_status == OrderStatus.PAID:
                updated = db.execute(
                    update(Order)
                    .where(Order.id == order.id, Order.status != OrderStatus.PAID)
                    .values(
                        **payment_success_values(
                            stripe_session_id=session_id or order.stripe_session_id,
                        )
                    )
                )
                db.commit()
                record_payment_event_best_effort(
                    db,
                    order_id=order.id,
                    event="stripe_payment_marked_paid"
                    if updated.rowcount
                    else "stripe_payment_paid_webhook_no_status_change",
                    provider="stripe",
                    source="stripe_webhook",
                    message="Stripe paid webhook resolved the order as paid.",
                    stripe_session_id=session_id or order.stripe_session_id,
                    stripe_event_id=event_id,
                    payment_intent_id=payment_intent_id,
                    context={
                        **_stripe_session_context(session, event_type=event_type),
                        "order_status_after": OrderStatus.PAID.value,
                        "updated_order": bool(updated.rowcount),
                    },
                    request=request,
                )
                if updated.rowcount:
                    email_payload = {
                        "order_id": order.id,
                        "total_cents": order.total_cents,
                        "currency": order.currency,
                        "email": order.email,
                        "phone": metadata.get("phone") or order.phone,
                        "items": [
                            {
                                "name": item.name,
                                "quantity": item.quantity,
                                "price_cents": item.price_cents,
                                "details": item.details,
                            }
                            for item in order.items
                        ],
                        "delivery_address": metadata.get("deliveryAddress")
                        or order.delivery_address,
                        "delivery_address_line1": metadata.get("deliveryAddressLine1")
                        or order.delivery_address_line1,
                        "delivery_address_line2": metadata.get("deliveryAddressLine2")
                        or order.delivery_address_line2,
                        "delivery_city": metadata.get("deliveryCity") or order.delivery_city,
                        "delivery_state": metadata.get("deliveryState") or order.delivery_state,
                        "delivery_postal_code": metadata.get("deliveryPostalCode")
                        or order.delivery_postal_code,
                        "delivery_country": metadata.get("deliveryCountry")
                        or order.delivery_country,
                        "delivery_floor": metadata.get("deliveryFloor") or order.delivery_floor,
                        "delivery_date_time": metadata.get("deliveryDateTime")
                        or order.delivery_date_time,
                        "order_comment": metadata.get("orderComment") or order.order_comment,
                        "delivery_miles": metadata.get("deliveryMiles")
                        or order.delivery_miles,
                        "delivery_fee": metadata.get("deliveryFeeCents")
                        or order.delivery_fee_cents,
                        "first_order_discount": metadata.get("firstOrderDiscountPercent")
                        or order.first_order_discount_percent,
                    }
                    try:
                        await send_admin_order_email(email_payload)
                        await send_customer_order_email(email_payload)
                    except Exception as exc:
                        log_critical_event(
                            domain="messaging",
                            event="order_email_delivery_failed",
                            message="Order confirmation email delivery failed after successful payment.",
                            request=request,
                            context={"order_id": order.id},
                            exc=exc,
                        )
            elif resolved_status == OrderStatus.FAILED:
                db.execute(
                    update(Order)
                    .where(Order.id == order.id, Order.status == OrderStatus.PENDING)
                    .values(
                        **payment_failure_values(
                            build_stripe_session_failure_diagnostics(
                                session,
                                event_type=event_type,
                            ),
                            stripe_session_id=session_id or order.stripe_session_id,
                        )
                    )
                )
                db.commit()
                record_payment_event_best_effort(
                    db,
                    order_id=order.id,
                    event="stripe_checkout_marked_failed",
                    provider="stripe",
                    source="stripe_webhook",
                    message="Stripe checkout webhook resolved the order as failed.",
                    stripe_session_id=session_id or order.stripe_session_id,
                    stripe_event_id=event_id,
                    payment_intent_id=payment_intent_id,
                    context={
                        **_stripe_session_context(session, event_type=event_type),
                        "order_status_after": OrderStatus.FAILED.value,
                    },
                    request=request,
                )
            else:
                payment_status = (session.get("payment_status") or "").lower()
                session_status = (session.get("status") or "").lower()
                currency = (session.get("currency") or "").lower()
                if session_status == "complete" and payment_status in {"paid", "no_payment_required"}:
                    log_critical_event(
                        domain="payment",
                        event="stripe_payment_data_mismatch",
                        message="Stripe paid session does not match order amount or currency.",
                        request=request,
                        context={
                            "order_id": order.id,
                            "amount_total": session.get("amount_total"),
                            "expected_total": order.total_cents,
                            "currency": currency,
                            "expected_currency": order.currency.lower(),
                        },
                    )
                    record_payment_event_best_effort(
                        db,
                        order_id=order.id,
                        event="stripe_payment_data_mismatch",
                        provider="stripe",
                        source="stripe_webhook",
                        message="Stripe paid session did not match order amount or currency.",
                        stripe_session_id=session_id or order.stripe_session_id,
                        stripe_event_id=event_id,
                        payment_intent_id=payment_intent_id,
                        context={
                            **_stripe_session_context(session, event_type=event_type),
                            "expected_total": order.total_cents,
                            "expected_currency": order.currency.lower(),
                        },
                        request=request,
                    )
                else:
                    record_payment_event_best_effort(
                        db,
                        order_id=order.id,
                        event="stripe_checkout_webhook_unresolved",
                        provider="stripe",
                        source="stripe_webhook",
                        message="Stripe checkout webhook did not resolve a final order status.",
                        stripe_session_id=session_id or order.stripe_session_id,
                        stripe_event_id=event_id,
                        payment_intent_id=payment_intent_id,
                        context=_stripe_session_context(session, event_type=event_type),
                        request=request,
                    )

    if event_type in ["checkout.session.expired", "checkout.session.async_payment_failed"]:
        session = event["data"]["object"]
        metadata = session.get("metadata") or {}
        order_id = metadata.get("orderId")
        session_id = session.get("id")
        payment_intent_id = _provider_id(session.get("payment_intent"))
        order = _load_order_for_session(db, order_id=order_id, session_id=session_id)
        if order and (
            not isinstance(session_id, str) or order.stripe_session_id != session_id
        ):
            log_critical_event(
                domain="payment",
                event="stripe_session_id_mismatch",
                message="Stripe failure webhook session id does not match stored order session id.",
                request=request,
                context={
                    "order_id": order.id,
                    "stripe_session_id": session_id,
                    "expected_stripe_session_id": order.stripe_session_id,
                },
            )
            order = None
        if order:
            record_payment_event_best_effort(
                db,
                order_id=order.id,
                event="stripe_webhook_received",
                provider="stripe",
                source="stripe_webhook",
                message=f"Stripe webhook received: {event_type}.",
                stripe_session_id=session_id or order.stripe_session_id,
                stripe_event_id=event_id,
                payment_intent_id=payment_intent_id,
                context={
                    **_stripe_session_context(session, event_type=event_type),
                    "order_status_before": order.status.value,
                },
                request=request,
            )
        if order and _can_record_payment_failure(order):
            db.execute(
                update(Order)
                .where(Order.id == order.id, Order.status == OrderStatus.PENDING)
                .values(
                    **payment_failure_values(
                        build_stripe_session_failure_diagnostics(
                            session,
                            event_type=event_type,
                        ),
                        stripe_session_id=session_id or order.stripe_session_id,
                    )
                )
            )
            db.commit()
            record_payment_event_best_effort(
                db,
                order_id=order.id,
                event="stripe_checkout_marked_failed",
                provider="stripe",
                source="stripe_webhook",
                message="Stripe failure webhook marked the checkout as failed.",
                stripe_session_id=session_id or order.stripe_session_id,
                stripe_event_id=event_id,
                payment_intent_id=payment_intent_id,
                context={
                    **_stripe_session_context(session, event_type=event_type),
                    "order_status_after": OrderStatus.FAILED.value,
                },
                request=request,
            )
        elif order:
            record_payment_event_best_effort(
                db,
                order_id=order.id,
                event="stripe_failure_webhook_ignored",
                provider="stripe",
                source="stripe_webhook",
                message="Stripe failure webhook was ignored because the order was no longer pending.",
                stripe_session_id=session_id or order.stripe_session_id,
                stripe_event_id=event_id,
                payment_intent_id=payment_intent_id,
                context={
                    **_stripe_session_context(session, event_type=event_type),
                    "order_status": order.status.value,
                },
                request=request,
            )
        elif not order:
            log_critical_event(
                domain="payment",
                event="webhook_order_not_found",
                message="Stripe failure webhook references unknown order.",
                request=request,
                context={"order_id": order_id, "stripe_session_id": session_id},
            )

    if event_type in ["payment_intent.payment_failed", "payment_intent.canceled"]:
        payment_intent = event["data"]["object"]
        metadata = payment_intent.get("metadata") or {}
        order_id = metadata.get("orderId")
        order = _load_order_for_session(db, order_id=order_id, session_id=None)
        payment_intent_id = payment_intent.get("id")
        if not order:
            log_critical_event(
                domain="payment",
                event="stripe_payment_intent_order_not_found",
                message="Stripe payment intent webhook references unknown order.",
                request=request,
                context={"order_id": order_id, "payment_intent_id": payment_intent_id},
            )
        else:
            record_payment_event_best_effort(
                db,
                order_id=order.id,
                event="stripe_webhook_received",
                provider="stripe",
                source="stripe_webhook",
                message=f"Stripe webhook received: {event_type}.",
                stripe_session_id=order.stripe_session_id,
                stripe_event_id=event_id,
                payment_intent_id=payment_intent_id,
                context={
                    **_stripe_payment_intent_context(
                        payment_intent, event_type=event_type
                    ),
                    "order_status_before": order.status.value,
                },
                request=request,
            )
        if order and order.status == OrderStatus.PENDING:
            db.execute(
                update(Order)
                .where(Order.id == order.id, Order.status == OrderStatus.PENDING)
                .values(
                    **payment_failure_values(
                        build_stripe_payment_intent_failure_diagnostics(
                            payment_intent,
                            event_type=event_type,
                        )
                    )
                )
            )
            db.commit()
            record_payment_event_best_effort(
                db,
                order_id=order.id,
                event="stripe_payment_intent_marked_failed",
                provider="stripe",
                source="stripe_webhook",
                message="Stripe PaymentIntent webhook marked the order as failed.",
                stripe_session_id=order.stripe_session_id,
                stripe_event_id=event_id,
                payment_intent_id=payment_intent_id,
                context={
                    **_stripe_payment_intent_context(
                        payment_intent, event_type=event_type
                    ),
                    "order_status_after": OrderStatus.FAILED.value,
                },
                request=request,
            )
        elif order:
            record_payment_event_best_effort(
                db,
                order_id=order.id,
                event="stripe_payment_intent_failure_ignored",
                provider="stripe",
                source="stripe_webhook",
                message="Stripe PaymentIntent failure webhook was ignored because the order was no longer pending.",
                stripe_session_id=order.stripe_session_id,
                stripe_event_id=event_id,
                payment_intent_id=payment_intent_id,
                context={
                    **_stripe_payment_intent_context(
                        payment_intent, event_type=event_type
                    ),
                    "order_status": order.status.value,
                },
                request=request,
            )

    mark_webhook_event_processed(db, provider="stripe", event_id=event_id)
    return {"received": True}
