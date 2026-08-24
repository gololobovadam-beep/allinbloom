from __future__ import annotations

from sqlalchemy import Column, DateTime, String, UniqueConstraint, func

from app.core.database import Base
from app.utils.ids import generate_cuid


class WebhookEvent(Base):
    __tablename__ = "WebhookEvent"
    __table_args__ = (UniqueConstraint("provider", "eventId", name="uq_WebhookEvent_provider_eventId"),)

    id = Column(String, primary_key=True, default=generate_cuid)
    provider = Column(String, nullable=False)
    event_id = Column("eventId", String, nullable=False)
    status = Column(String, nullable=False, default="PROCESSING", server_default="PROCESSING")
    claimed_at = Column(
        "claimedAt", DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    processed_at = Column("processedAt", DateTime(timezone=True), nullable=True)
    created_at = Column("createdAt", DateTime(timezone=True), server_default=func.now(), nullable=False)
