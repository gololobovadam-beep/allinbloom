from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import case, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enums import OrderStatus
from app.models.order import Order
from app.models.payment_ledger_entry import PaymentLedgerEntry


@dataclass(frozen=True)
class RefundApplicationResult:
    recorded: bool
    state_updated: bool
    reason: str | None
    refunded_cents: int
    status: OrderStatus


class _RefundStateRejected(RuntimeError):
    pass


def record_provider_ledger_entry_once(
    db: Session,
    *,
    order_id: str,
    provider: str,
    entry_type: str,
    external_reference: str,
    amount_cents: int,
    currency: str,
    source_event_id: str | None = None,
) -> bool:
    """Record a provider financial fact exactly once in the current transaction.

    A nested transaction makes a duplicate financial object harmless without
    rolling back the caller's order transition.  The outer transaction is
    intentionally left to the caller so order status and ledger entry commit
    atomically.
    """
    if not external_reference.strip():
        raise ValueError("A provider financial reference is required.")
    if amount_cents <= 0:
        raise ValueError("Ledger amount must be positive.")
    if not currency.strip():
        raise ValueError("Ledger currency is required.")

    try:
        with db.begin_nested():
            db.add(
                PaymentLedgerEntry(
                    order_id=order_id,
                    provider=provider,
                    entry_type=entry_type,
                    external_reference=external_reference,
                    amount_cents=amount_cents,
                    currency=currency.upper(),
                    source_event_id=source_event_id,
                )
            )
            db.flush()
        return True
    except IntegrityError:
        # The unique provider/reference constraint is the monetary replay
        # guard. Do not count a second event for the same provider object.
        return False


def apply_provider_refund_once(
    db: Session,
    *,
    order: Order,
    provider: str,
    external_reference: str,
    amount_cents: int,
    currency: str,
    source_event_id: str | None = None,
) -> RefundApplicationResult:
    """Append one refund fact and atomically advance the order total once.

    The conditional SQL increment prevents two different partial-refund
    webhooks from losing each other's amount. A duplicate provider refund
    object never changes the order a second time.
    """
    if amount_cents <= 0:
        raise ValueError("Refund amount must be positive.")

    protected_statuses = (OrderStatus.CHARGEBACK, OrderStatus.REVERSED)
    if order.status in protected_statuses:
        recorded = record_provider_ledger_entry_once(
            db,
            order_id=order.id,
            provider=provider,
            entry_type="refund",
            external_reference=external_reference,
            amount_cents=amount_cents,
            currency=currency,
            source_event_id=source_event_id,
        )
        return RefundApplicationResult(
            recorded=recorded,
            state_updated=False,
            reason="state_protected",
            refunded_cents=int(order.refunded_cents or 0),
            status=order.status,
        )

    try:
        with db.begin_nested():
            db.add(
                PaymentLedgerEntry(
                    order_id=order.id,
                    provider=provider,
                    entry_type="refund",
                    external_reference=external_reference,
                    amount_cents=amount_cents,
                    currency=currency.upper(),
                    source_event_id=source_event_id,
                )
            )
            db.flush()

            next_total = Order.refunded_cents + amount_cents
            updated = db.execute(
                update(Order)
                .where(
                    Order.id == order.id,
                    Order.status.notin_(protected_statuses),
                    next_total <= Order.total_cents,
                )
                .values(
                    refunded_cents=next_total,
                    status=case(
                        # A refund may settle while a dispute is still open;
                        # retain the dispute state until its own lifecycle
                        # event resolves it, while preserving the total.
                        (Order.status == OrderStatus.DISPUTED, OrderStatus.DISPUTED),
                        (next_total == Order.total_cents, OrderStatus.REFUNDED),
                        else_=OrderStatus.PARTIALLY_REFUNDED,
                    ),
                )
            )
            if not updated.rowcount:
                raise _RefundStateRejected
            db.flush()
    except IntegrityError:
        # A unique provider/reference collision is the expected duplicate
        # replay path. The savepoint has already rolled back safely.
        db.refresh(order)
        return RefundApplicationResult(
            recorded=False,
            state_updated=False,
            reason="duplicate",
            refunded_cents=int(order.refunded_cents or 0),
            status=order.status,
        )
    except _RefundStateRejected:
        db.refresh(order)
        next_total = int(order.refunded_cents or 0) + amount_cents
        reason = (
            "refund_total_exceeded"
            if next_total > order.total_cents
            else "state_protected"
            if order.status in protected_statuses
            else "state_conflict"
        )
        return RefundApplicationResult(
            recorded=False,
            state_updated=False,
            reason=reason,
            refunded_cents=int(order.refunded_cents or 0),
            status=order.status,
        )

    db.refresh(order)
    return RefundApplicationResult(
        recorded=True,
        state_updated=True,
        reason=None,
        refunded_cents=int(order.refunded_cents or 0),
        status=order.status,
    )
