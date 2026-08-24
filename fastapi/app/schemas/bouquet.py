from __future__ import annotations

from typing import Optional

from pydantic import AliasChoices, Field, field_validator, model_validator

from app.models.enums import BouquetType, CatalogType, FlowerType
from app.schemas.base import SchemaBase


MAX_GALLERY_IMAGES = 50
MAX_IMAGE_URL_LENGTH = 2048
MAX_VIDEO_URL_LENGTH = 2048
MAX_TIER_TITLE_LENGTH = 200
MAX_TIER_DESCRIPTION_LENGTH = 1200


class EventTierIn(SchemaBase):
    price_cents: int = Field(ge=0, le=100_000_000)
    title: Optional[str] = Field(default=None, max_length=MAX_TIER_TITLE_LENGTH)
    description: str = Field(min_length=1, max_length=MAX_TIER_DESCRIPTION_LENGTH)

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Tier description is required.")
        return normalized

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class EventTierOut(EventTierIn):
    id: str


class CatalogCategoryOut(SchemaBase):
    id: str
    catalog_type: CatalogType
    slug: str
    name: str
    position: int
    is_active: bool


class BouquetOut(SchemaBase):
    """Backward-compatible response for every catalog product.

    The historical response fields remain available for flowers.  New clients
    should use ``catalogType``, ``galleryImages``, ``videoUrl`` and ``tiers``.
    """

    id: str
    catalog_type: CatalogType = CatalogType.FLOWERS
    category_id: Optional[str] = None
    category: CatalogCategoryOut | None = None
    name: str
    description: str
    price_cents: int
    currency: str
    flower_type: FlowerType
    style: str
    bouquet_type: BouquetType
    colors: str
    is_mixed: bool
    is_featured: bool
    is_active: bool
    is_sold_out: bool = False
    allow_flower_quantity: bool
    default_flower_quantity: int = 1
    discount_percent: int
    discount_note: Optional[str] = None
    video_url: Optional[str] = None
    video_orientation: str = "HORIZONTAL"
    gallery_images: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices(
            "gallery_images", "galleryImages", "gallery_image_urls"
        ),
        serialization_alias="galleryImages",
    )
    tiers: list[EventTierOut] = Field(
        default_factory=list,
        validation_alias=AliasChoices("tiers", "event_tiers"),
        serialization_alias="tiers",
    )
    image: str
    image_2: Optional[str] = None
    image_3: Optional[str] = None
    image_4: Optional[str] = None
    image_5: Optional[str] = None
    image_6: Optional[str] = None


class _BouquetPayloadBase(SchemaBase):
    name: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=5000)
    price_cents: Optional[int] = Field(default=None, ge=0, le=100_000_000)
    currency: Optional[str] = Field(default=None, max_length=8)
    flower_type: Optional[FlowerType] = None
    style: Optional[str] = Field(default=None, max_length=500)
    bouquet_type: Optional[BouquetType] = None
    colors: Optional[str] = Field(default=None, max_length=1000)
    is_mixed: Optional[bool] = None
    is_featured: Optional[bool] = None
    is_active: Optional[bool] = None
    is_sold_out: Optional[bool] = None
    allow_flower_quantity: Optional[bool] = None
    default_flower_quantity: Optional[int] = Field(default=None, ge=1, le=1001)
    discount_percent: Optional[int] = Field(default=None, ge=0, le=90)
    discount_note: Optional[str] = Field(default=None, max_length=500)
    image: Optional[str] = Field(default=None, max_length=MAX_IMAGE_URL_LENGTH)
    image_2: Optional[str] = Field(default=None, max_length=MAX_IMAGE_URL_LENGTH)
    image_3: Optional[str] = Field(default=None, max_length=MAX_IMAGE_URL_LENGTH)
    image_4: Optional[str] = Field(default=None, max_length=MAX_IMAGE_URL_LENGTH)
    image_5: Optional[str] = Field(default=None, max_length=MAX_IMAGE_URL_LENGTH)
    image_6: Optional[str] = Field(default=None, max_length=MAX_IMAGE_URL_LENGTH)
    catalog_type: Optional[CatalogType] = None
    category_id: Optional[str] = Field(default=None, max_length=128)
    video_url: Optional[str] = Field(default=None, max_length=MAX_VIDEO_URL_LENGTH)
    video_orientation: Optional[str] = Field(default=None, max_length=10)
    gallery_images: Optional[list[str]] = Field(
        default=None,
        max_length=MAX_GALLERY_IMAGES,
        validation_alias=AliasChoices("gallery_images", "galleryImages"),
        serialization_alias="galleryImages",
    )
    tiers: Optional[list[EventTierIn]] = Field(
        default=None,
        max_length=50,
        validation_alias=AliasChoices("tiers"),
        serialization_alias="tiers",
    )

    @field_validator(
        "name",
        "description",
        "currency",
        "style",
        "colors",
        "discount_note",
        "image",
        "image_2",
        "image_3",
        "image_4",
        "image_5",
        "image_6",
        "category_id",
        "video_url",
        mode="before",
    )
    @classmethod
    def strip_optional_text(cls, value: object) -> object:
        if value is None:
            return None
        return str(value).strip()

    @field_validator("currency")
    @classmethod
    def require_usd_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if normalized != "USD":
            raise ValueError("Only USD catalog prices are supported.")
        return normalized

    @field_validator("video_orientation")
    @classmethod
    def validate_video_orientation(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if normalized not in {"HORIZONTAL", "VERTICAL"}:
            raise ValueError("Video orientation must be HORIZONTAL or VERTICAL.")
        return normalized

    @field_validator("gallery_images")
    @classmethod
    def validate_gallery_length(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if len(value) > MAX_GALLERY_IMAGES:
            raise ValueError(f"At most {MAX_GALLERY_IMAGES} gallery images are allowed.")
        return value


class BouquetCreate(_BouquetPayloadBase):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    price_cents: Optional[int] = Field(default=None, ge=0, le=100_000_000)
    currency: str = "USD"
    flower_type: Optional[FlowerType] = None
    style: Optional[str] = None
    bouquet_type: Optional[BouquetType] = BouquetType.MONO
    colors: Optional[str] = ""
    is_mixed: bool = False
    is_featured: bool = False
    is_active: bool = True
    is_sold_out: bool = False
    allow_flower_quantity: bool = True
    default_flower_quantity: int = 1
    discount_percent: int = Field(default=0, ge=0, le=90)
    discount_note: Optional[str] = None
    image: Optional[str] = None
    catalog_type: CatalogType = CatalogType.FLOWERS
    video_orientation: str = "HORIZONTAL"

    @model_validator(mode="after")
    def validate_catalog_specific_values(self):
        has_gallery = bool(self.gallery_images)
        if not (self.image or has_gallery):
            raise ValueError("At least one image is required.")

        if self.catalog_type == CatalogType.FLOWERS:
            if self.flower_type is None:
                raise ValueError("Flower type is required for flowers.")
            if not (self.style or "").strip():
                raise ValueError("Flower style is required for flowers.")
            if self.price_cents is None or self.price_cents <= 0:
                raise ValueError("Price must be greater than 0 for flowers.")
        elif self.catalog_type in {CatalogType.BALOONS, CatalogType.GIFTS}:
            if self.price_cents is None or self.price_cents <= 0:
                raise ValueError("Price must be greater than 0 for purchasable products.")
        elif self.catalog_type == CatalogType.EVENT_SPACE:
            # Event Space cards are booked through Instagram, so the legacy
            # non-null price column remains neutral whether or not tiers exist.
            if self.price_cents not in {None, 0}:
                raise ValueError("Event Space pricing must be configured through tiers.")
            self.price_cents = 0

        if self.catalog_type != CatalogType.EVENT_SPACE and self.tiers:
            raise ValueError("Tiers are only available for Event Space.")

        if self.video_url and self.catalog_type not in {
            CatalogType.GIFTS,
            CatalogType.EVENT_SPACE,
        }:
            raise ValueError("Video is only available for gifts and Event Space.")
        return self


class BouquetUpdate(_BouquetPayloadBase):
    """Partial update. Catalog-type invariants are enforced by the route."""
