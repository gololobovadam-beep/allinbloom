from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

import stripe
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.models.order import Order
from app.models.enums import OrderStatus
from app.services.payment_diagnostics import (
    apply_order_values,
    build_paypal_failure_diagnostics,
    build_stripe_session_failure_diagnostics,
    build_timeout_failure_diagnostics,
    payment_failure_values,
    payment_success_values,
)
from app.services.payment_events import record_payment_event_best_effort
from app.services.payment_notifications import (
    enqueue_order_confirmation_notifications,
    mark_order_paid,
)
from app.services.paypal import (
    PayPalApiError,
    paypal_capture_order,
    paypal_extract_order_metadata,
    paypal_get_order,
    paypal_is_configured,
)
from app.utils.admin_orders import get_day_range, get_week_range

PENDING_EXPIRATION_HOURS = 24
PENDING_WITHOUT_SESSION_EXPIRATION_MINUTES = 10
STRIPE_CHECKOUT_SESSION_EXPIRATION_SECONDS = 30 * 60
PAYPAL_CHECKOUT_EXPIRATION_SECONDS = 10 * 60


def _read_stripe_attr(obj: object, key: str) -> object:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _provider_id(value: object) -> str | None:
    if not value:
        return None
    if isinstance(value, str):
        return value
    nested_id = _read_stripe_attr(value, "id")
    return str(nested_id) if nested_id else None


def _extract_payment_intent_status(payment_intent: object) -> str | None:
    if not payment_intent:
        return None

    if isinstance(payment_intent, str):
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent)
        except Exception:
            return None
        status = getattr(intent, "status", None)
    elif isinstance(payment_intent, dict):
        status = payment_intent.get("status")
    else:
        status = getattr(payment_intent, "status", None)

    if not status:
        return None
    return str(status).lower()


def _is_order_older_than(order: Order, *, seconds: int) -> bool:
    created_at = order.created_at
    if not isinstance(created_at, datetime):
        return False
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    if now <= created_at:
        return False
    return (now - created_at).total_seconds() > seconds


def resolve_order_status_from_session(
    order: Order, session: object, now_seconds: int | None = None
) -> OrderStatus | None:
    metadata_raw = _read_stripe_attr(session, "metadata") or {}
    metadata_order_id = (
        metadata_raw.get("orderId") if isinstance(metadata_raw, dict) else None
    )
    session_id = _read_stripe_attr(session, "id")
    # A paid provider object is authoritative only when every stable binding
    # points back to the order created by this application.
    if metadata_order_id != order.id:
        return None
    if not isinstance(session_id, str) or session_id != order.stripe_session_id:
        return None

    session_status = str(_read_stripe_attr(session, "status") or "").lower()
    payment_status = str(_read_stripe_attr(session, "payment_status") or "").lower()
    amount_total = _read_stripe_attr(session, "amount_total")
    currency = str(_read_stripe_attr(session, "currency") or "").lower()

    amount_matches = isinstance(amount_total, int) and amount_total == order.total_cents
    currency_matches = currency == order.currency.lower()

    if (
        session_status == "complete"
        and payment_status in {"paid", "no_payment_required"}
        and amount_matches
        and currency_matches
    ):
        if payment_status == "no_payment_required" and amount_total not in {0, None}:
            return None
        return OrderStatus.PAID

    if session_status == "expired":
        return OrderStatus.FAILED

    if now_seconds is None:
        now_seconds = int(datetime.now(timezone.utc).timestamp())
    expires_at = _read_stripe_attr(session, "expires_at")
    if isinstance(expires_at, int) and expires_at < now_seconds:
        return OrderStatus.FAILED

    if session_status == "complete" and payment_status == "unpaid":
        payment_intent = _read_stripe_attr(session, "payment_intent")
        intent_status = _extract_payment_intent_status(payment_intent)
        if intent_status == "succeeded" and amount_matches and currency_matches:
            return OrderStatus.PAID
        # A Checkout PaymentIntent can fail and be retried while the Checkout
        # session is still open. Only an expired session or explicit async
        # failure webhook may close the order.

    return None


def expire_pending_orders(db: Session) -> None:
    now = datetime.now(timezone.utc)
    cutoff_without_session = now - timedelta(
        minutes=PENDING_WITHOUT_SESSION_EXPIRATION_MINUTES
    )
    expired_order_ids = (
        db.execute(
            select(Order.id).where(
                Order.status == OrderStatus.PENDING,
                Order.stripe_session_id.is_(None),
                Order.paypal_order_id.is_(None),
                Order.is_deleted.is_(False),
                Order.created_at < cutoff_without_session,
            )
        )
        .scalars()
        .all()
    )

    db.execute(
        update(Order)
        .where(
            Order.status == OrderStatus.PENDING,
            Order.stripe_session_id.is_(None),
            Order.paypal_order_id.is_(None),
            Order.is_deleted.is_(False),
            Order.created_at < cutoff_without_session,
        )
        .values(
            **payment_failure_values(
                build_timeout_failure_diagnostics(has_provider_session=False)
            )
        )
    )
    db.commit()
    for order_id in expired_order_ids:
        record_payment_event_best_effort(
            db,
            order_id=order_id,
            event="checkout_setup_timed_out",
            provider="checkout",
            source="server_sync",
            message="Pending order timed out before a provider payment session was linked.",
            context={
                "order_status_after": OrderStatus.FAILED.value,
                "timeout_minutes": PENDING_WITHOUT_SESSION_EXPIRATION_MINUTES,
            },
        )


def _sync_with_stripe(db: Session, orders: Iterable[Order]) -> dict[str, OrderStatus]:
    if not settings.stripe_secret_key:
        return {}
    stripe.api_key = settings.stripe_secret_key
    updates: dict[str, OrderStatus] = {}
    sync_events: list[dict[str, object]] = []
    now_seconds = int(datetime.now(timezone.utc).timestamp())

    for order in orders:
        if order.status != OrderStatus.PENDING or not order.stripe_session_id:
            continue
        try:
            session = stripe.checkout.Session.retrieve(order.stripe_session_id)
        except Exception:
            continue

        next_status = resolve_order_status_from_session(
            order, session, now_seconds=now_seconds
        )
        if next_status and next_status != order.status:
            payment_intent_id = _provider_id(_read_stripe_attr(session, "payment_intent"))
            values = (
                payment_success_values(stripe_payment_intent_id=payment_intent_id)
                if next_status == OrderStatus.PAID
                else payment_failure_values(build_stripe_session_failure_diagnostics(session))
            )
            updated = db.execute(
                update(Order)
                .where(Order.id == order.id, Order.status == OrderStatus.PENDING)
                .values(**values)
            )
            if not updated.rowcount:
                continue
            if next_status == OrderStatus.PAID:
                enqueue_order_confirmation_notifications(db, order_id=order.id)
            apply_order_values(order, values)
            updates[order.id] = next_status
            sync_events.append(
                {
                    "order_id": order.id,
                    "next_status": next_status,
                    "stripe_session_id": order.stripe_session_id,
                    "payment_intent_id": payment_intent_id,
                    "session_status": _read_stripe_attr(session, "status"),
                    "payment_status": _read_stripe_attr(session, "payment_status"),
                    "expires_at": _read_stripe_attr(session, "expires_at"),
                }
            )

    if updates:
        db.commit()
        for item in sync_events:
            next_status = item["next_status"]
            assert isinstance(next_status, OrderStatus)
            record_payment_event_best_effort(
                db,
                order_id=str(item["order_id"]),
                event=(
                    "stripe_sync_marked_paid"
                    if next_status == OrderStatus.PAID
                    else "stripe_sync_marked_failed"
                ),
                provider="stripe",
                source="server_sync",
                message="Server-side Stripe sync resolved the order status.",
                stripe_session_id=item.get("stripe_session_id"),
                payment_intent_id=item.get("payment_intent_id"),
                context={
                    "order_status_after": next_status.value,
                    "session_status": item.get("session_status"),
                    "payment_status": item.get("payment_status"),
                    "expires_at": item.get("expires_at"),
                },
            )
    return updates


def resolve_order_status_from_paypal_order(
    order: Order, payload: dict
) -> tuple[OrderStatus | None, str | None]:
    metadata = paypal_extract_order_metadata(payload)
    custom_id = metadata.get("custom_id")
    amount_cents = metadata.get("amount_cents")
    currency = metadata.get("currency")
    status = metadata.get("status")
    capture_id = metadata.get("capture_id")
    capture_status = metadata.get("capture_status")

    if custom_id != order.id:
        return None, None
    if not isinstance(amount_cents, int) or amount_cents != order.total_cents:
        return None, None
    if not isinstance(currency, str) or currency.upper() != order.currency.upper():
        return None, None

    if status == "COMPLETED" or capture_status == "COMPLETED":
        return OrderStatus.PAID, capture_id
    if status in {"VOIDED", "CANCELED", "CANCELLED"} or capture_status in {
        "DECLINED",
        "DENIED",
        "FAILED",
    }:
        return OrderStatus.FAILED, capture_id
    if status in {
        "CREATED",
        "SAVED",
        "PAYER_ACTION_REQUIRED",
        "APPROVED",
    } and _is_order_older_than(order, seconds=PAYPAL_CHECKOUT_EXPIRATION_SECONDS):
        return OrderStatus.FAILED, capture_id
    if capture_status == "PENDING" and _is_order_older_than(
        order, seconds=PAYPAL_CHECKOUT_EXPIRATION_SECONDS
    ):
        return OrderStatus.FAILED, capture_id
    return None, None


def _sync_with_paypal(db: Session, orders: Iterable[Order]) -> dict[str, OrderStatus]:
    if not paypal_is_configured():
        return {}

    updates: dict[str, OrderStatus] = {}
    sync_events: list[dict[str, object]] = []

    for order in orders:
        if order.status != OrderStatus.PENDING or not order.paypal_order_id:
            continue
        try:
            payload = paypal_get_order(order.paypal_order_id)
        except PayPalApiError:
            continue

        status = (payload.get("status") or "").upper()
        if status == "APPROVED":
            try:
                payload = paypal_capture_order(order.paypal_order_id, request_id=order.id)
            except PayPalApiError as exc:
                if exc.status_code is None or exc.status_code >= 500:
                    continue
                try:
                    payload = paypal_get_order(order.paypal_order_id)
                except PayPalApiError:
                    continue

        next_status, capture_id = resolve_order_status_from_paypal_order(order, payload)
        if next_status and next_status != order.status:
            values = (
                payment_success_values(
                    paypal_capture_id=capture_id or order.paypal_capture_id,
                )
                if next_status == OrderStatus.PAID
                else payment_failure_values(
                    build_paypal_failure_diagnostics(payload),
                    paypal_capture_id=capture_id or order.paypal_capture_id,
                )
            )
            updated = db.execute(
                update(Order)
                .where(Order.id == order.id, Order.status == OrderStatus.PENDING)
                .values(**values)
            )
            if not updated.rowcount:
                continue
            if next_status == OrderStatus.PAID:
                enqueue_order_confirmation_notifications(db, order_id=order.id)
            apply_order_values(order, values)
            updates[order.id] = next_status
            sync_events.append(
                {
                    "order_id": order.id,
                    "next_status": next_status,
                    "paypal_order_id": order.paypal_order_id,
                    "paypal_capture_id": capture_id,
                    "paypal_status": payload.get("status"),
                }
            )

    if updates:
        db.commit()
        for item in sync_events:
            next_status = item["next_status"]
            assert isinstance(next_status, OrderStatus)
            record_payment_event_best_effort(
                db,
                order_id=str(item["order_id"]),
                event=(
                    "paypal_sync_marked_paid"
                    if next_status == OrderStatus.PAID
                    else "paypal_sync_marked_failed"
                ),
                provider="paypal",
                source="server_sync",
                message="Server-side PayPal sync resolved the order status.",
                context={
                    "order_status_after": next_status.value,
                    "paypal_order_id": item.get("paypal_order_id"),
                    "paypal_capture_id": item.get("paypal_capture_id"),
                    "paypal_status": item.get("paypal_status"),
                },
            )
    return updates


def sync_order_with_stripe_payload(
    db: Session, order: Order, session: object
) -> OrderStatus | None:
    """Apply a previously fetched Stripe Checkout session to one order.

    Keeping provider I/O separate lets async routes fetch via a thread pool
    without moving a SQLAlchemy session across threads.
    """
    if order.status != OrderStatus.PENDING or not order.stripe_session_id:
        return None
    next_status = resolve_order_status_from_session(order, session)
    if not next_status or next_status == order.status:
        return None

    payment_intent_id = _provider_id(_read_stripe_attr(session, "payment_intent"))
    if next_status == OrderStatus.PAID:
        if not mark_order_paid(
            db,
            order,
            stripe_payment_intent_id=payment_intent_id,
        ):
            return None
    else:
        values = payment_failure_values(build_stripe_session_failure_diagnostics(session))
        updated = db.execute(
            update(Order)
            .where(Order.id == order.id, Order.status == OrderStatus.PENDING)
            .values(**values)
        )
        if not updated.rowcount:
            return None
        db.commit()
        apply_order_values(order, values)
    record_payment_event_best_effort(
        db,
        order_id=order.id,
        event=(
            "stripe_sync_marked_paid"
            if next_status == OrderStatus.PAID
            else "stripe_sync_marked_failed"
        ),
        provider="stripe",
        source="server_sync",
        message="Server-side Stripe sync resolved the order status.",
        stripe_session_id=order.stripe_session_id,
        payment_intent_id=payment_intent_id,
        context={
            "order_status_after": next_status.value,
            "session_status": _read_stripe_attr(session, "status"),
            "payment_status": _read_stripe_attr(session, "payment_status"),
            "expires_at": _read_stripe_attr(session, "expires_at"),
        },
    )
    return next_status


def sync_order_with_stripe(db: Session, order: Order) -> OrderStatus | None:
    if (
        order.status != OrderStatus.PENDING
        or not order.stripe_session_id
        or not settings.stripe_secret_key
    ):
        return None

    stripe.api_key = settings.stripe_secret_key
    try:
        session = stripe.checkout.Session.retrieve(order.stripe_session_id)
    except Exception:
        return None
    return sync_order_with_stripe_payload(db, order, session)


def sync_order_with_paypal_payload(
    db: Session, order: Order, payload: dict
) -> OrderStatus | None:
    """Apply a previously fetched PayPal payload to one order."""
    if order.status != OrderStatus.PENDING or not order.paypal_order_id:
        return None
    next_status, capture_id = resolve_order_status_from_paypal_order(order, payload)
    if not next_status or next_status == order.status:
        return None

    if next_status == OrderStatus.PAID:
        if not mark_order_paid(
            db,
            order,
            paypal_capture_id=capture_id or order.paypal_capture_id,
        ):
            return None
    else:
        values = payment_failure_values(
            build_paypal_failure_diagnostics(payload),
            paypal_capture_id=capture_id or order.paypal_capture_id,
        )
        updated = db.execute(
            update(Order)
            .where(Order.id == order.id, Order.status == OrderStatus.PENDING)
            .values(**values)
        )
        if not updated.rowcount:
            return None
        db.commit()
        apply_order_values(order, values)
    record_payment_event_best_effort(
        db,
        order_id=order.id,
        event=(
            "paypal_sync_marked_paid"
            if next_status == OrderStatus.PAID
            else "paypal_sync_marked_failed"
        ),
        provider="paypal",
        source="server_sync",
        message="Server-side PayPal sync resolved the order status.",
        context={
            "order_status_after": next_status.value,
            "paypal_order_id": order.paypal_order_id,
            "paypal_capture_id": capture_id,
            "paypal_status": payload.get("status"),
        },
    )
    return next_status


def sync_order_with_paypal(db: Session, order: Order) -> OrderStatus | None:
    if (
        order.status != OrderStatus.PENDING
        or not order.paypal_order_id
        or not paypal_is_configured()
    ):
        return None

    try:
        payload = paypal_get_order(order.paypal_order_id)
    except PayPalApiError:
        return None

    status = (payload.get("status") or "").upper()
    if status == "APPROVED":
        try:
            payload = paypal_capture_order(order.paypal_order_id, request_id=order.id)
        except PayPalApiError as exc:
            if exc.status_code is None or exc.status_code >= 500:
                return None
            try:
                payload = paypal_get_order(order.paypal_order_id)
            except PayPalApiError:
                return None

    return sync_order_with_paypal_payload(db, order, payload)


def sync_pending_orders(db: Session, *, limit: int = 200) -> dict[str, OrderStatus]:
    expire_pending_orders(db)
    safe_limit = max(limit, 1)
    orders = (
        db.execute(
            select(Order)
            .where(
                Order.status == OrderStatus.PENDING,
                Order.is_deleted.is_(False),
                or_(
                    Order.stripe_session_id.is_not(None),
                    Order.paypal_order_id.is_not(None),
                ),
            )
            .order_by(Order.created_at.asc())
            .limit(safe_limit)
        )
        .scalars()
        .all()
    )
    if not orders:
        return {}

    stripe_updates = _sync_with_stripe(db, orders)
    paypal_updates = _sync_with_paypal(db, orders)
    updates = {**stripe_updates, **paypal_updates}
    if updates:
        for order in orders:
            if order.id in updates:
                order.status = updates[order.id]
    return updates


def get_admin_orders(db: Session) -> list[Order]:
    expire_pending_orders(db)
    orders = (
        db.execute(
            select(Order)
            .where(Order.is_deleted.is_(False))
            .options(joinedload(Order.items))
            .order_by(Order.created_at.desc())
        )
        .unique()
        .scalars()
        .all()
    )
    stripe_updates = _sync_with_stripe(db, orders)
    paypal_updates = _sync_with_paypal(db, orders)
    updates = {**stripe_updates, **paypal_updates}
    if not updates:
        return orders
    for order in orders:
        if order.id in updates:
            order.status = updates[order.id]
    return orders


def get_admin_orders_by_day(
    db: Session, day_key: str, only_deleted: bool = False
) -> list[Order]:
    expire_pending_orders(db)
    day_range = get_day_range(day_key)
    if not day_range:
        return []
    orders = (
        db.execute(
            select(Order)
            .where(
                Order.created_at >= day_range["start"],
                Order.created_at < day_range["end"],
                Order.is_deleted.is_(only_deleted),
            )
            .options(joinedload(Order.items))
            .order_by(Order.created_at.desc())
        )
        .unique()
        .scalars()
        .all()
    )
    stripe_updates = _sync_with_stripe(db, orders)
    paypal_updates = _sync_with_paypal(db, orders)
    updates = {**stripe_updates, **paypal_updates}
    if not updates:
        return orders
    for order in orders:
        if order.id in updates:
            order.status = updates[order.id]
    return orders


def get_admin_orders_by_week(
    db: Session, week_start_key: str, only_deleted: bool = False
) -> list[Order]:
    expire_pending_orders(db)
    week_range = get_week_range(week_start_key)
    if not week_range:
        return []
    orders = (
        db.execute(
            select(Order)
            .where(
                Order.created_at >= week_range["start"],
                Order.created_at < week_range["end"],
                Order.is_deleted.is_(only_deleted),
            )
            .options(joinedload(Order.items))
            .order_by(Order.created_at.desc())
        )
        .unique()
        .scalars()
        .all()
    )
    stripe_updates = _sync_with_stripe(db, orders)
    paypal_updates = _sync_with_paypal(db, orders)
    updates = {**stripe_updates, **paypal_updates}
    if not updates:
        return orders
    for order in orders:
        if order.id in updates:
            order.status = updates[order.id]
    return orders


def get_admin_orders_page(
    db: Session,
    only_deleted: bool = False,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Order], bool, int | None]:
    expire_pending_orders(db)
    safe_offset = max(offset, 0)
    safe_limit = max(limit, 1)
    order_ids = (
        db.execute(
            select(Order.id)
            .where(Order.is_deleted.is_(only_deleted))
            .order_by(Order.created_at.desc(), Order.id.desc())
            .offset(safe_offset)
            .limit(safe_limit + 1)
        )
        .scalars()
        .all()
    )
    has_more = len(order_ids) > safe_limit
    page_order_ids = order_ids[:safe_limit]
    if not page_order_ids:
        return [], False, None

    orders = (
        db.execute(
            select(Order)
            .where(Order.id.in_(page_order_ids))
            .options(joinedload(Order.items))
        )
        .unique()
        .scalars()
        .all()
    )
    orders_by_id = {order.id: order for order in orders}
    sorted_orders = [
        orders_by_id[order_id]
        for order_id in page_order_ids
        if order_id in orders_by_id
    ]
    stripe_updates = _sync_with_stripe(db, sorted_orders)
    paypal_updates = _sync_with_paypal(db, sorted_orders)
    updates = {**stripe_updates, **paypal_updates}
    if updates:
        for order in sorted_orders:
            if order.id in updates:
                order.status = updates[order.id]

    next_offset = safe_offset + safe_limit if has_more else None
    return sorted_orders, has_more, next_offset


def get_orders_by_email(db: Session, email: str) -> list[Order]:
    expire_pending_orders(db)
    orders = (
        db.execute(
            select(Order)
            .where(Order.email == email)
            .options(joinedload(Order.items))
            .order_by(Order.created_at.desc())
        )
        .unique()
        .scalars()
        .all()
    )
    stripe_updates = _sync_with_stripe(db, orders)
    paypal_updates = _sync_with_paypal(db, orders)
    updates = {**stripe_updates, **paypal_updates}
    if not updates:
        return orders
    for order in orders:
        if order.id in updates:
            order.status = updates[order.id]
    return orders
