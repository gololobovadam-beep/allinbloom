from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging

from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.critical_logging import log_critical_event
from app.models.enums import OrderStatus
from app.models.notification_outbox import NotificationOutbox
from app.models.order import Order
from app.services.email import send_admin_order_email, send_customer_order_email
from app.services.payment_diagnostics import apply_order_values, payment_success_values


logger = logging.getLogger(__name__)

ORDER_CONFIRMATION_ADMIN = "order_confirmation_admin"
ORDER_CONFIRMATION_CUSTOMER = "order_confirmation_customer"
_DELIVERY_EVENTS = (ORDER_CONFIRMATION_ADMIN, ORDER_CONFIRMATION_CUSTOMER)
_LEASE_SECONDS = 5 * 60
_MAX_DELIVERY_ATTEMPTS = 12


def _email_payload(order: Order) -> dict:
    return {
        "order_id": order.id,
        "total_cents": order.total_cents,
        "currency": order.currency,
        "email": order.email,
        "phone": order.phone,
        "items": [
            {
                "name": item.name,
                "quantity": item.quantity,
                "price_cents": item.price_cents,
                "details": item.details,
            }
            for item in order.items
        ],
        "delivery_address": order.delivery_address,
        "delivery_address_line1": order.delivery_address_line1,
        "delivery_address_line2": order.delivery_address_line2,
        "delivery_city": order.delivery_city,
        "delivery_state": order.delivery_state,
        "delivery_postal_code": order.delivery_postal_code,
        "delivery_country": order.delivery_country,
        "delivery_floor": order.delivery_floor,
        "delivery_date_time": order.delivery_date_time,
        "order_comment": order.order_comment,
        "delivery_miles": order.delivery_miles,
        "delivery_fee": order.delivery_fee_cents,
        "first_order_discount": order.first_order_discount_percent,
    }


def enqueue_order_confirmation_notifications(db: Session, *, order_id: str) -> None:
    """Enqueue each confirmation recipient exactly once in the current transaction."""
    for event in _DELIVERY_EVENTS:
        try:
            # A savepoint lets a concurrent webhook win the unique key without
            # rolling back the paid status transition that surrounds this call.
            with db.begin_nested():
                db.add(NotificationOutbox(order_id=order_id, event=event))
                db.flush()
        except IntegrityError:
            logger.debug(
                "Notification already queued for order=%s event=%s", order_id, event
            )


def mark_order_paid(
    db: Session,
    order: Order,
    *,
    commit: bool = True,
    **extra_values: object,
) -> bool:
    """Atomically persist PAID and durable confirmation work.

    Only PENDING orders may transition to paid. This protects refund/dispute
    states from a delayed or reordered successful-payment webhook.
    """
    values = payment_success_values(**extra_values)
    updated = db.execute(
        update(Order)
        .where(Order.id == order.id, Order.status == OrderStatus.PENDING)
        .values(**values)
    )
    if not updated.rowcount:
        return False

    enqueue_order_confirmation_notifications(db, order_id=order.id)
    if commit:
        db.commit()
        db.refresh(order)
    else:
        apply_order_values(order, values)
    return True


def _claim_next_notification(db: Session) -> NotificationOutbox | None:
    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(seconds=_LEASE_SECONDS)
    candidates = (
        db.execute(
            select(NotificationOutbox)
            .where(
                or_(
                    and_(
                        NotificationOutbox.status.in_(("PENDING", "RETRY")),
                        NotificationOutbox.available_at <= now,
                    ),
                    and_(
                        NotificationOutbox.status == "SENDING",
                        NotificationOutbox.locked_at <= stale_before,
                    ),
                ),
                NotificationOutbox.attempt_count < _MAX_DELIVERY_ATTEMPTS,
            )
            .order_by(NotificationOutbox.available_at.asc(), NotificationOutbox.created_at.asc())
            .limit(8)
        )
        .scalars()
        .all()
    )
    for candidate in candidates:
        claimed = db.execute(
            update(NotificationOutbox)
            .execution_options(synchronize_session=False)
            .where(
                NotificationOutbox.id == candidate.id,
                or_(
                    NotificationOutbox.status.in_(("PENDING", "RETRY")),
                    and_(
                        NotificationOutbox.status == "SENDING",
                        NotificationOutbox.locked_at <= stale_before,
                    ),
                ),
            )
            .values(
                status="SENDING",
                locked_at=now,
                attempt_count=NotificationOutbox.attempt_count + 1,
                last_error=None,
            )
        )
        if claimed.rowcount:
            db.commit()
            return db.get(NotificationOutbox, candidate.id)
    db.rollback()
    return None


def _retry_delay(attempt_count: int) -> timedelta:
    # 1m, 2m, 4m ... capped at one hour. Delivery stays observable rather
    # than being silently swallowed by a webhook request.
    seconds = min(60 * (2 ** max(attempt_count - 1, 0)), 60 * 60)
    return timedelta(seconds=seconds)


async def dispatch_pending_order_notifications(db: Session, *, limit: int = 10) -> int:
    """Best-effort immediate delivery; failures remain queued for a worker."""
    delivered = 0
    for _ in range(max(limit, 0)):
        entry = _claim_next_notification(db)
        if not entry:
            break

        order = (
            db.execute(
                select(Order)
                .where(Order.id == entry.order_id)
                .options(joinedload(Order.items))
            )
            .unique()
            .scalars()
            .first()
        )
        if not order or order.status != OrderStatus.PAID:
            db.execute(
                update(NotificationOutbox)
                .where(NotificationOutbox.id == entry.id)
                .values(
                    status="CANCELED",
                    locked_at=None,
                    last_error="Order is missing or is no longer in PAID state.",
                )
            )
            db.commit()
            continue

        try:
            payload = _email_payload(order)
            if entry.event == ORDER_CONFIRMATION_ADMIN:
                await send_admin_order_email(payload)
            elif entry.event == ORDER_CONFIRMATION_CUSTOMER:
                await send_customer_order_email(payload)
            else:
                raise ValueError(f"Unsupported notification event: {entry.event}")
        except Exception as exc:
            retry_at = datetime.now(timezone.utc) + _retry_delay(entry.attempt_count)
            db.execute(
                update(NotificationOutbox)
                .where(NotificationOutbox.id == entry.id)
                .values(
                    status="RETRY",
                    locked_at=None,
                    available_at=retry_at,
                    last_error=str(exc)[:500],
                )
            )
            db.commit()
            log_critical_event(
                domain="messaging",
                event="order_notification_delivery_failed",
                message="Order confirmation notification was queued for retry.",
                context={"order_id": order.id, "notification_event": entry.event},
                exc=exc,
                level=logging.WARNING,
            )
            continue

        db.execute(
            update(NotificationOutbox)
            .where(NotificationOutbox.id == entry.id)
            .values(
                status="SENT",
                sent_at=datetime.now(timezone.utc),
                locked_at=None,
                last_error=None,
            )
        )
        db.commit()
        delivered += 1
    return delivered
