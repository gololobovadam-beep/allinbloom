from __future__ import annotations

from typing import Optional

from pydantic import AliasChoices, Field, model_validator

from app.schemas.base import SchemaBase


class StoreSettingsOut(SchemaBase):
    id: str
    global_discount_percent: int
    global_discount_note: Optional[str] = None
    category_discount_percent: int
    category_discount_note: Optional[str] = None
    category_flower_type: Optional[str] = None
    category_style: Optional[str] = None
    category_mixed: Optional[str] = None
    category_color: Optional[str] = None
    category_min_price_cents: Optional[int] = None
    category_max_price_cents: Optional[int] = None
    first_order_discount_percent: int
    first_order_discount_note: Optional[str] = None
    home_hero_image: str
    home_gallery_image_1: str
    home_gallery_image_2: str
    home_gallery_image_3: str
    home_gallery_image_4: str
    home_gallery_image_5: str
    home_gallery_image_6: str
    home_gallery_images: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices(
            "home_gallery_images", "homeGalleryImages", "home_gallery_urls"
        ),
        serialization_alias="homeGalleryImages",
    )
    catalog_category_image_mono: str
    catalog_category_image_mixed: str
    catalog_category_image_season: str
    catalog_category_image_all: str
    shop_all_image_flowers: str
    shop_all_image_balloons: str
    shop_all_image_gift_box: str
    shop_all_image_event_space: str


class StoreSettingsUpdate(SchemaBase):
    global_discount_percent: Optional[int] = Field(default=None, ge=0, le=90)
    global_discount_note: Optional[str] = Field(default=None, max_length=500)
    category_discount_percent: Optional[int] = Field(default=None, ge=0, le=90)
    category_discount_note: Optional[str] = Field(default=None, max_length=500)
    category_flower_type: Optional[str] = Field(default=None, max_length=64)
    category_style: Optional[str] = Field(default=None, max_length=128)
    category_mixed: Optional[str] = Field(default=None, max_length=32)
    category_color: Optional[str] = Field(default=None, max_length=128)
    category_min_price_cents: Optional[int] = Field(default=None, ge=0, le=100_000_000)
    category_max_price_cents: Optional[int] = Field(default=None, ge=0, le=100_000_000)
    first_order_discount_percent: Optional[int] = Field(default=None, ge=0, le=90)
    first_order_discount_note: Optional[str] = Field(default=None, max_length=500)
    home_hero_image: Optional[str] = Field(default=None, max_length=2048)
    home_gallery_image_1: Optional[str] = Field(default=None, max_length=2048)
    home_gallery_image_2: Optional[str] = Field(default=None, max_length=2048)
    home_gallery_image_3: Optional[str] = Field(default=None, max_length=2048)
    home_gallery_image_4: Optional[str] = Field(default=None, max_length=2048)
    home_gallery_image_5: Optional[str] = Field(default=None, max_length=2048)
    home_gallery_image_6: Optional[str] = Field(default=None, max_length=2048)
    home_gallery_images: Optional[list[str]] = Field(
        default=None,
        max_length=50,
        validation_alias=AliasChoices("home_gallery_images", "homeGalleryImages"),
        serialization_alias="homeGalleryImages",
    )
    catalog_category_image_mono: Optional[str] = Field(default=None, max_length=2048)
    catalog_category_image_mixed: Optional[str] = Field(default=None, max_length=2048)
    catalog_category_image_season: Optional[str] = Field(default=None, max_length=2048)
    catalog_category_image_all: Optional[str] = Field(default=None, max_length=2048)
    shop_all_image_flowers: Optional[str] = Field(default=None, max_length=2048)
    shop_all_image_balloons: Optional[str] = Field(default=None, max_length=2048)
    shop_all_image_gift_box: Optional[str] = Field(default=None, max_length=2048)
    shop_all_image_event_space: Optional[str] = Field(default=None, max_length=2048)

    @model_validator(mode="after")
    def validate_price_range(self):
        if (
            self.category_min_price_cents is not None
            and self.category_max_price_cents is not None
            and self.category_min_price_cents > self.category_max_price_cents
        ):
            raise ValueError("Minimum category price cannot exceed maximum category price.")
        return self
