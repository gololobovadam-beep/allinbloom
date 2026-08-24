from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Index, JSON, String, func

from app.core.database import Base
from app.utils.ids import generate_cuid


class PaymentEvent(Base):
    __tablename__ = "PaymentEvent"
    __table_args__ = (
        Index("ix_PaymentEvent_orderId_createdAt", "orderId", "createdAt"),
    )

    id = Column(String, primary_key=True, default=generate_cuid)
    order_id = Column(
        "orderId",
        String,
        # Payment events are the audit trail for a financial operation. Do
        # not let an administrative order deletion erase that evidence.
        ForeignKey("Order.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    provider = Column(String, nullable=False, default="checkout")
    source = Column(String, nullable=False, default="server")
    event = Column(String, nullable=False)
    message = Column(String, nullable=True)
    stripe_session_id = Column("stripeSessionId", String, nullable=True, index=True)
    stripe_event_id = Column("stripeEventId", String, nullable=True, index=True)
    payment_intent_id = Column("paymentIntentId", String, nullable=True, index=True)
    context = Column(JSON, nullable=True)
    created_at = Column(
        "createdAt", DateTime(timezone=True), server_default=func.now(), nullable=False
    )
