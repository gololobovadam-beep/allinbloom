from __future__ import annotations

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)

from app.core.database import Base
from app.utils.ids import generate_cuid


class PaymentLedgerEntry(Base):
    """An immutable provider-side financial fact.

    Webhook delivery IDs are only unique per notification.  A provider can
    legitimately emit multiple notifications for one refund, so the durable
    provider reference is the idempotency key for monetary state changes.
    """

    __tablename__ = "PaymentLedgerEntry"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "externalReference",
            name="uq_PaymentLedgerEntry_provider_externalReference",
        ),
        Index("ix_PaymentLedgerEntry_orderId_createdAt", "orderId", "createdAt"),
    )

    id = Column(String, primary_key=True, default=generate_cuid)
    order_id = Column(
        "orderId",
        String,
        ForeignKey("Order.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    provider = Column(String, nullable=False)
    entry_type = Column("entryType", String, nullable=False)
    # This is scoped by provider and includes the financial object kind, e.g.
    # ``refund:PAYPAL_REFUND_ID``. It is never a raw webhook delivery id.
    external_reference = Column("externalReference", String, nullable=False)
    amount_cents = Column("amountCents", Integer, nullable=False)
    currency = Column(String, nullable=False)
    source_event_id = Column("sourceEventId", String, nullable=True, index=True)
    created_at = Column(
        "createdAt", DateTime(timezone=True), server_default=func.now(), nullable=False
    )
