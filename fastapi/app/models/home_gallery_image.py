from __future__ import annotations

from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.utils.ids import generate_cuid


class HomeGalleryImage(Base):
    """Ordered homepage gallery image for the singleton store settings row."""

    __tablename__ = "HomeGalleryImage"
    __table_args__ = (
        UniqueConstraint(
            "storeSettingsId",
            "position",
            name="uq_HomeGalleryImage_storeSettingsId_position",
        ),
        CheckConstraint("position >= 0", name="ck_HomeGalleryImage_position_nonnegative"),
    )

    id = Column(String, primary_key=True, default=generate_cuid)
    store_settings_id = Column(
        "storeSettingsId",
        String,
        ForeignKey("StoreSettings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url = Column(String, nullable=False)
    position = Column(Integer, nullable=False)

    store_settings = relationship("StoreSettings", back_populates="home_gallery_image_rows")
