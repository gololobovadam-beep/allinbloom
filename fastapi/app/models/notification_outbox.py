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


class NotificationOutbox(Base):
    """Durable, idempotent delivery queue for payment-related notifications."""

    __tablename__ = "NotificationOutbox"
    __table_args__ = (
        UniqueConstraint("orderId", "event", name="uq_NotificationOutbox_orderId_event"),
        Index("ix_NotificationOutbox_status_availableAt", "status", "availableAt"),
    )

    id = Column(String, primary_key=True, default=generate_cuid)
    order_id = Column(
        "orderId",
        String,
        ForeignKey("Order.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Separate events are used for the customer and administrator so retrying
    # one recipient cannot duplicate delivery to the other.
    event = Column(String, nullable=False)
    status = Column(String, nullable=False, default="PENDING", server_default="PENDING")
    attempt_count = Column("attemptCount", Integer, nullable=False, default=0, server_default="0")
    available_at = Column(
        "availableAt", DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    locked_at = Column("lockedAt", DateTime(timezone=True), nullable=True)
    sent_at = Column("sentAt", DateTime(timezone=True), nullable=True)
    last_error = Column("lastError", String, nullable=True)
    created_at = Column(
        "createdAt", DateTime(timezone=True), server_default=func.now(), nullable=False
    )
