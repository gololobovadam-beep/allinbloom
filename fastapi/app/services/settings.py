from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.store_settings import StoreSettings
from app.services.catalog_products import replace_home_gallery_images
from app.services.colors import normalize_color_value


DEFAULT_SETTINGS = {
    "id": "default",
    "global_discount_percent": 0,
    "global_discount_note": None,
    "category_discount_percent": 0,
    "category_discount_note": None,
    "category_flower_type": None,
    "category_style": None,
    "category_mixed": None,
    "category_color": None,
    "category_min_price_cents": None,
    "category_max_price_cents": None,
    "first_order_discount_percent": 10,
    "first_order_discount_note": "10% off your first order",
    "home_hero_image": "/images/hero-bouquet.webp",
    "home_gallery_image_1": "/images/bouquet-1.webp",
    "home_gallery_image_2": "/images/bouquet-2.webp",
    "home_gallery_image_3": "/images/bouquet-3.webp",
    "home_gallery_image_4": "/images/bouquet-4.webp",
    "home_gallery_image_5": "/images/bouquet-5.webp",
    "home_gallery_image_6": "/images/bouquet-6.webp",
    "catalog_category_image_mono": "/images/bouquet-7.webp",
    "catalog_category_image_mixed": "/images/bouquet-5.webp",
    "catalog_category_image_season": "/images/bouquet-2.webp",
    "catalog_category_image_all": "/images/hero-bouquet.webp",
}


def get_store_settings(db: Session) -> StoreSettings:
    settings = db.get(StoreSettings, "default")
    if settings:
        normalized_category_color = normalize_color_value(settings.category_color)
        if settings.category_color and normalized_category_color != settings.category_color:
            settings.category_color = normalized_category_color
            db.commit()
            db.refresh(settings)
        return settings
    settings = StoreSettings(**DEFAULT_SETTINGS)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def update_store_settings(db: Session, data: dict) -> StoreSettings:
    settings = get_store_settings(db)
    home_gallery_images = data.pop("home_gallery_images", None)
    legacy_home_keys = (
        "home_gallery_image_1",
        "home_gallery_image_2",
        "home_gallery_image_3",
        "home_gallery_image_4",
        "home_gallery_image_5",
        "home_gallery_image_6",
    )
    # Existing admin clients still submit six named fields.  Mirror such
    # updates into the normalized relation so its preferred read path does not
    # mask legacy edits during the compatibility window.
    if home_gallery_images is None and any(key in data for key in legacy_home_keys):
        home_gallery_images = [
            data.get(key, getattr(settings, key)) for key in legacy_home_keys
        ]
    if "category_color" in data:
        data["category_color"] = normalize_color_value(data.get("category_color"))
    for key, value in data.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    if home_gallery_images is not None:
        replace_home_gallery_images(settings, home_gallery_images)
    db.commit()
    db.refresh(settings)
    return settings
