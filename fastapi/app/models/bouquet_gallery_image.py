from __future__ import annotations

from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.utils.ids import generate_cuid


class BouquetGalleryImage(Base):
    """An ordered gallery image belonging to any catalog product."""

    __tablename__ = "BouquetGalleryImage"
    __table_args__ = (
        UniqueConstraint("bouquetId", "position", name="uq_BouquetGalleryImage_bouquetId_position"),
        CheckConstraint("position >= 0", name="ck_BouquetGalleryImage_position_nonnegative"),
    )

    id = Column(String, primary_key=True, default=generate_cuid)
    bouquet_id = Column(
        "bouquetId",
        String,
        ForeignKey("Bouquet.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url = Column(String, nullable=False)
    position = Column(Integer, nullable=False)

    bouquet = relationship("Bouquet", back_populates="gallery_image_rows")
