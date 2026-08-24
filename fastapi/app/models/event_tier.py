from __future__ import annotations

from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.utils.ids import generate_cuid


class EventTier(Base):
    """A price/description tier configured for an Event Space product."""

    __tablename__ = "EventTier"
    __table_args__ = (
        UniqueConstraint("bouquetId", "position", name="uq_EventTier_bouquetId_position"),
        CheckConstraint("position >= 0", name="ck_EventTier_position_nonnegative"),
        CheckConstraint('"priceCents" >= 0', name="ck_EventTier_price_nonnegative"),
    )

    id = Column(String, primary_key=True, default=generate_cuid)
    bouquet_id = Column(
        "bouquetId",
        String,
        ForeignKey("Bouquet.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    price_cents = Column("priceCents", Integer, nullable=False)
    title = Column(String(200), nullable=True)
    description = Column(String, nullable=False)
    position = Column(Integer, nullable=False)

    bouquet = relationship("Bouquet", back_populates="event_tiers")
