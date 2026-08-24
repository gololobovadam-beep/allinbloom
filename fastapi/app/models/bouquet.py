from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.enums import BouquetType, CatalogType, FlowerType
from app.utils.ids import generate_cuid


class Bouquet(Base):
    __tablename__ = "Bouquet"
    __table_args__ = (
        CheckConstraint(
            '"catalogType" IN (\'FLOWERS\', \'BALOONS\', \'GIFTS\', \'EVENT_SPACE\')',
            name="ck_Bouquet_catalogType",
        ),
        CheckConstraint('"currency" = \'USD\'', name="ck_Bouquet_currency_usd"),
    )

    id = Column(String, primary_key=True, default=generate_cuid)
    # The legacy table is now the common backing store for all catalog entries.
    # Keeping its name preserves the existing OrderItem.bouquetId foreign key.
    catalog_type = Column(
        "catalogType", String, default=CatalogType.FLOWERS.value, nullable=False, index=True
    )
    category_id = Column(
        "categoryId",
        String,
        ForeignKey("CatalogCategory.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    price_cents = Column("priceCents", Integer, nullable=False)
    currency = Column(String, default="USD", nullable=False)
    flower_type = Column("flowerType", Enum(FlowerType, name="FlowerType"), nullable=False)
    # Stores up to three flower types as CSV (e.g. "ROSE, TULIP").
    style = Column(String, nullable=False)
    bouquet_type = Column("bouquetType", String, default=BouquetType.MONO.value, nullable=False)
    colors = Column(String, nullable=False)
    is_mixed = Column("isMixed", Boolean, default=False, nullable=False)
    is_featured = Column("isFeatured", Boolean, default=False, nullable=False)
    is_active = Column("isActive", Boolean, default=True, nullable=False)
    is_sold_out = Column("isSoldOut", Boolean, default=False, nullable=False)
    allow_flower_quantity = Column(
        "allowFlowerQuantity", Boolean, default=True, nullable=False
    )
    default_flower_quantity = Column(
        "defaultFlowerQuantity", Integer, default=1, nullable=False
    )
    discount_percent = Column("discountPercent", Integer, default=0, nullable=False)
    discount_note = Column("discountNote", String, nullable=True)
    video_url = Column("videoUrl", String, nullable=True)
    video_orientation = Column("videoOrientation", String(10), default="HORIZONTAL", nullable=False)
    image = Column(String, nullable=False)
    image_2 = Column("image2", String, nullable=True)
    image_3 = Column("image3", String, nullable=True)
    image_4 = Column("image4", String, nullable=True)
    image_5 = Column("image5", String, nullable=True)
    image_6 = Column("image6", String, nullable=True)
    created_at = Column(
        "createdAt", DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        "updatedAt",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    category = relationship("CatalogCategory", back_populates="bouquets")
    gallery_image_rows = relationship(
        "BouquetGalleryImage",
        back_populates="bouquet",
        cascade="all, delete-orphan",
        order_by="BouquetGalleryImage.position",
    )
    event_tiers = relationship(
        "EventTier",
        back_populates="bouquet",
        cascade="all, delete-orphan",
        order_by="EventTier.position",
    )
    order_items = relationship("OrderItem", back_populates="bouquet")

    @property
    def gallery_image_urls(self) -> list[str]:
        """Relation-backed gallery with a temporary legacy-column fallback."""

        relation_urls = [
            str(row.url or "").strip()
            for row in (self.gallery_image_rows or [])
            if str(row.url or "").strip()
        ]
        candidates = relation_urls or [
            str(value or "").strip()
            for value in (
                self.image,
                self.image_2,
                self.image_3,
                self.image_4,
                self.image_5,
                self.image_6,
            )
            if str(value or "").strip()
        ]
        return list(dict.fromkeys(candidates))

    @property
    def gallery_images(self) -> list[str]:
        """Schema-facing alias for the normalized gallery URL list."""

        return self.gallery_image_urls
