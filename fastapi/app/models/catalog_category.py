from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.utils.ids import generate_cuid


class CatalogCategory(Base):
    """Optional, ordered category for a top-level catalog.

    Current balloon catalog intentionally has no persisted category: the
    storefront's ``All`` view is represented by ``category_id is NULL``.
    Keeping this table now lets categories be introduced later without another
    product-table redesign.
    """

    __tablename__ = "CatalogCategory"
    __table_args__ = (
        UniqueConstraint("catalogType", "slug", name="uq_CatalogCategory_catalogType_slug"),
        CheckConstraint(
            '"catalogType" IN (\'FLOWERS\', \'BALOONS\', \'GIFTS\', \'EVENT_SPACE\')',
            name="ck_CatalogCategory_catalogType",
        ),
    )

    id = Column(String, primary_key=True, default=generate_cuid)
    catalog_type = Column("catalogType", String, nullable=False, index=True)
    slug = Column(String, nullable=False)
    name = Column(String, nullable=False)
    position = Column(Integer, nullable=False, default=0)
    is_active = Column("isActive", Boolean, nullable=False, default=True)
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

    bouquets = relationship("Bouquet", back_populates="category")
