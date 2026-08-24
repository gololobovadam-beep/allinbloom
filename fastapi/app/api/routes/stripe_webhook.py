from __future__ import annotations

import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import case, or_, select, update
from sqlalchemy.orm import Session, joinedload
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_db
from app.core.config import settings
from app.core.critical_logging import log_critical_event
from app.models.order import Order
from app.models.enums import OrderStatus
from app.services.payment_diagnostics import (
    build_stripe_payment_intent_failure_diagnostics,
    build_stripe_session_failure_diagnostics,
    payment_attempt_failure_values,
    payment_failure_values,
)
from app.services.payment_events import record_payment_event_best_effort
from app.services.payment_notifications import (
    dispatch_pending_order_notifications,
    mark_order_paid,
)
from app.services.orders import resolve_order_status_from_session
from app.services.webhook_events import (
    claim_webhook_event,
    mark_webhook_event_processed,
    release_webhook_event_claim,
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


def _load_order_for_stripe_payment(
    db: Session,
    *,
    payment_intent_id: str | None = None,
    charge_id: str | None = None,
) -> Order | None:
    conditions = []
    if payment_intent_id:
        conditions.append(Order.stripe_payment_intent_id == payment_intent_id)
    if charge_id:
        conditions.append(Order.stripe_charge_id == charge_id)
    if not conditions:
        return None
    return (
        db.execute(select(Order).where(or_(*conditions)).options(joinedload(Order.items)))
        .unique()
        .scalars()
        .first()
    )


async def _resolve_order_for_stripe_charge(
    db: Session, *, charge_id: str | None
) -> Order | None:
    """Resolve a charge event even when success has not linked its charge.

    Stripe can deliver independent event streams out of order. The fallback
    uses Stripe's immutable charge -> PaymentIntent -> application metadata
    binding rather than silently dropping a financial dispute.
    """
    order = _load_order_for_stripe_payment(db, charge_id=charge_id)
    if order or not charge_id:
        return order

    try:
        charge = await run_in_threadpool(stripe.Charge.retrieve, charge_id)
    except Exception:
        return None

    payment_intent_id = _provider_id(_read_provider_attr(charge, "payment_intent"))
    metadata = _read_provider_attr(charge, "metadata") or {}
    order_id = metadata.get("orderId") if isinstance(metadata, dict) else None
    order = _load_order_for_stripe_payment(
        db, payment_intent_id=payment_intent_id, charge_id=charge_id
    )

    if not order and payment_intent_id:
        try:
            payment_intent = await run_in_threadpool(
                stripe.PaymentIntent.retrieve, payment_intent_id
            )
        except Exception:
            payment_intent = None
        intent_metadata = _read_provider_attr(payment_intent, "metadata") or {}
        intent_order_id = (
            intent_metadata.get("orderId")
            if isinstance(intent_metadata, dict)
            else None
        )
        order = _load_order_for_session(
            db,
            order_id=intent_order_id if isinstance(intent_order_id, str) else order_id,
            session_id=None,
        )
    elif not order and isinstance(order_id, str):
        order = _load_order_for_session(db, order_id=order_id, session_id=None)

    if not order:
        return None

    charge_amount = _read_provider_attr(charge, "amount")
    charge_currency = _read_provider_attr(charge, "currency")
    if (
        not _stripe_amount_matches(order, charge_amount, charge_currency)
        or charge_amount != order.total_cents
    ):
        return None
    if (
        order.stripe_payment_intent_id
        and payment_intent_id
        and order.stripe_payment_intent_id != payment_intent_id
    ):
        return None
    if order.stripe_charge_id and order.stripe_charge_id != charge_id:
        return None

    values: dict[str, object] = {}
    if payment_intent_id and not order.stripe_payment_intent_id:
        values["stripe_payment_intent_id"] = payment_intent_id
    if not order.stripe_charge_id:
        values["stripe_charge_id"] = charge_id
    if values:
        try:
            db.execute(update(Order).where(Order.id == order.id).values(**values))
            db.commit()
            db.refresh(order)
        except Exception:
            db.rollback()
            return None
    return order


def _stripe_amount_matches(order: Order, value: object, currency: object) -> bool:
    return (
        isinstance(value, int)
        and value >= 0
        and isinstance(currency, str)
        and currency.upper() == order.currency.upper()
    )


def _status_after_dispute_won(order: Order) -> OrderStatus:
    refunded_cents = int(order.refunded_cents or 0)
    if refunded_cents >= order.total_cents:
        return OrderStatus.REFUNDED
    if refunded_cents > 0:
        return OrderStatus.PARTIALLY_REFUNDED
    return OrderStatus.PAID


def _record_stripe_lifecycle_event(
    db: Session,
    *,
    order: Order,
    event_id: str,
    event_type: str,
    message: str,
    payment_intent_id: str | None = None,
    charge_id: str | None = None,
    context: dict[str, object] | None = None,
    request: Request | None = None,
) -> None:
    record_payment_event_best_effort(
        db,
        order_id=order.id,
        event=event_type,
        provider="stripe",
        source="stripe_webhook",
        message=message,
        stripe_session_id=order.stripe_session_id,
        stripe_event_id=event_id,
        payment_intent_id=payment_intent_id or order.stripe_payment_intent_id,
        context={
            "stripe_charge_id": charge_id or order.stripe_charge_id,
            "order_status_after": order.status.value,
            **(context or {}),
        },
        request=request,
    )


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

    if not claim_webhook_event(db, provider="stripe", event_id=event_id):
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
                updated = mark_order_paid(
                    db,
                    order,
                    stripe_session_id=session_id or order.stripe_session_id,
                    stripe_payment_intent_id=payment_intent_id,
                )
                record_payment_event_best_effort(
                    db,
                    order_id=order.id,
                    event="stripe_payment_marked_paid"
                    if updated
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
                        "updated_order": updated,
                    },
                    request=request,
                )
                if updated:
                    await dispatch_pending_order_notifications(db, limit=2)
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
                    **payment_attempt_failure_values(
                        build_stripe_payment_intent_failure_diagnostics(
                            payment_intent,
                            event_type=event_type,
                        ),
                        stripe_payment_intent_id=payment_intent_id,
                    )
                )
            )
            db.commit()
            record_payment_event_best_effort(
                db,
                order_id=order.id,
                event="stripe_payment_intent_attempt_failed",
                provider="stripe",
                source="stripe_webhook",
                message="Stripe PaymentIntent failure was recorded while Checkout remains retryable.",
                stripe_session_id=order.stripe_session_id,
                stripe_event_id=event_id,
                payment_intent_id=payment_intent_id,
                context={
                    **_stripe_payment_intent_context(
                        payment_intent, event_type=event_type
                    ),
                    "order_status_after": OrderStatus.PENDING.value,
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

    if event_type == "payment_intent.succeeded":
        payment_intent = event["data"]["object"]
        metadata = payment_intent.get("metadata") or {}
        order_id = metadata.get("orderId")
        payment_intent_id = _provider_id(payment_intent)
        charge_id = _provider_id(payment_intent.get("latest_charge"))
        order = _load_order_for_session(db, order_id=order_id, session_id=None)
        amount = payment_intent.get("amount")
        currency = payment_intent.get("currency")
        if order and _stripe_amount_matches(order, amount, currency) and amount == order.total_cents:
            db.execute(
                update(Order)
                .where(Order.id == order.id)
                .values(
                    stripe_payment_intent_id=payment_intent_id,
                    stripe_charge_id=charge_id or order.stripe_charge_id,
                )
            )
            db.commit()
            db.refresh(order)
            _record_stripe_lifecycle_event(
                db,
                order=order,
                event_id=event_id,
                event_type="stripe_payment_intent_succeeded",
                message="Stripe PaymentIntent identifiers were linked to the order.",
                payment_intent_id=payment_intent_id,
                charge_id=charge_id,
                request=request,
            )

    if event_type == "charge.refunded":
        charge = event["data"]["object"]
        payment_intent_id = _provider_id(charge.get("payment_intent"))
        charge_id = _provider_id(charge)
        order = _load_order_for_stripe_payment(
            db,
            payment_intent_id=payment_intent_id,
            charge_id=charge_id,
        )
        if not order:
            order = await _resolve_order_for_stripe_charge(db, charge_id=charge_id)
        if not order:
            log_critical_event(
                domain="payment",
                event="stripe_refund_order_unresolved",
                message="Stripe refund could not be bound to an order and will be retried.",
                request=request,
                context={
                    "stripe_event_id": event_id,
                    "stripe_charge_id": charge_id,
                    "payment_intent_id": payment_intent_id,
                },
            )
            release_webhook_event_claim(db, provider="stripe", event_id=event_id)
            raise HTTPException(status_code=502, detail="Unable to process Stripe refund.")
        amount_refunded = charge.get("amount_refunded")
        currency = charge.get("currency")
        if _stripe_amount_matches(order, amount_refunded, currency):
            if amount_refunded > order.total_cents:
                log_critical_event(
                    domain="payment",
                    event="stripe_refund_amount_mismatch",
                    message="Stripe refund exceeds the original order total.",
                    request=request,
                    context={
                        "order_id": order.id,
                        "amount_refunded": amount_refunded,
                        "expected_total": order.total_cents,
                    },
                )
            else:
                next_status = (
                    OrderStatus.REFUNDED
                    if amount_refunded >= order.total_cents
                    else OrderStatus.PARTIALLY_REFUNDED
                )
                db.execute(
                    update(Order)
                    .where(
                        Order.id == order.id,
                        Order.status.notin_((OrderStatus.CHARGEBACK, OrderStatus.REVERSED)),
                    )
                    .values(
                        status=case(
                            (Order.status == OrderStatus.DISPUTED, OrderStatus.DISPUTED),
                            else_=next_status,
                        ),
                        refunded_cents=amount_refunded,
                        stripe_payment_intent_id=payment_intent_id or order.stripe_payment_intent_id,
                        stripe_charge_id=charge_id or order.stripe_charge_id,
                    )
                )
                db.commit()
                db.refresh(order)
                _record_stripe_lifecycle_event(
                    db,
                    order=order,
                    event_id=event_id,
                    event_type="stripe_charge_refunded",
                    message="Stripe reported a charge refund.",
                    payment_intent_id=payment_intent_id,
                    charge_id=charge_id,
                    context={"refunded_cents": amount_refunded},
                    request=request,
                )

    if event_type.startswith("charge.dispute."):
        dispute = event["data"]["object"]
        charge_id = _provider_id(dispute.get("charge"))
        order = await _resolve_order_for_stripe_charge(db, charge_id=charge_id)
        if not order:
            # Never acknowledge an unbound dispute as processed. A retry can
            # succeed after a delayed PaymentIntent/session linkage, and the
            # critical log is visible to reconciliation if it cannot.
            log_critical_event(
                domain="payment",
                event="stripe_dispute_order_unresolved",
                message="Stripe dispute could not be bound to an order and will be retried.",
                request=request,
                context={"stripe_event_id": event_id, "stripe_charge_id": charge_id},
            )
            release_webhook_event_claim(db, provider="stripe", event_id=event_id)
            raise HTTPException(status_code=502, detail="Unable to process Stripe dispute.")

        outcome = str(dispute.get("status") or dispute.get("outcome") or "").lower()
        if event_type == "charge.dispute.closed" and outcome in {"lost", "lost_dispute"}:
            next_status = OrderStatus.CHARGEBACK
        elif event_type == "charge.dispute.closed" and outcome in {"won", "won_dispute"}:
            next_status = (
                _status_after_dispute_won(order)
                if order.status == OrderStatus.DISPUTED
                else order.status
            )
        else:
            next_status = OrderStatus.DISPUTED
        db.execute(
            update(Order)
            .where(Order.id == order.id)
            .values(status=next_status, stripe_charge_id=charge_id or order.stripe_charge_id)
        )
        db.commit()
        db.refresh(order)
        _record_stripe_lifecycle_event(
            db,
            order=order,
            event_id=event_id,
            event_type=event_type,
            message="Stripe dispute lifecycle event was recorded.",
            charge_id=charge_id,
            context={"dispute_status": outcome},
            request=request,
        )

    mark_webhook_event_processed(db, provider="stripe", event_id=event_id)
    return {"received": True}
