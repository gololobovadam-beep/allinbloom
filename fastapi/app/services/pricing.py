from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.services.colors import normalize_color_value, normalize_palette_text


@dataclass
class DiscountInfo:
    percent: int
    note: str
    source: str


def clamp_percent(value: int) -> int:
    return max(0, min(90, round(value)))


def _catalog_type_value(bouquet) -> str:
    raw = getattr(bouquet, "catalog_type", "FLOWERS")
    return str(getattr(raw, "value", raw) or "FLOWERS").upper()


def apply_percent_discount(price_cents: int, percent: int) -> int:
    clamped = clamp_percent(percent)
    return max(0, round(price_cents * (100 - clamped) / 100))


def _has_category_filters(settings) -> bool:
    return any(
        [
            settings.category_flower_type,
            settings.category_mixed,
            settings.category_color,
            settings.category_min_price_cents is not None,
            settings.category_max_price_cents is not None,
        ]
    )


def _matches_category(bouquet, settings) -> bool:
    # Existing category-discount controls describe flower attributes.  Do not
    # accidentally apply them to balloons/gifts that carry neutral legacy
    # flower fields for database compatibility.
    catalog_type = _catalog_type_value(bouquet)
    if catalog_type != "FLOWERS":
        return False
    if settings.category_discount_percent <= 0:
        return False
    if not _has_category_filters(settings):
        return False

    if settings.category_flower_type and settings.category_flower_type != bouquet.flower_type:
        return False
    bouquet_type = str(getattr(bouquet, "bouquet_type", "") or "").strip().lower()
    if settings.category_mixed == "mixed":
        if bouquet_type:
            if bouquet_type != "mixed":
                return False
        elif not bouquet.is_mixed:
            return False
    if settings.category_mixed == "mono":
        if bouquet_type:
            if bouquet_type != "mono":
                return False
        elif bouquet.is_mixed:
            return False
    if settings.category_mixed == "season":
        if bouquet_type != "season":
            return False
    if settings.category_color:
        palette = normalize_palette_text(bouquet.colors)
        needle = normalize_color_value(settings.category_color) or settings.category_color.lower()
        if needle not in palette:
            return False
    if (
        settings.category_min_price_cents is not None
        and bouquet.price_cents < settings.category_min_price_cents
    ):
        return False
    if (
        settings.category_max_price_cents is not None
        and bouquet.price_cents > settings.category_max_price_cents
    ):
        return False
    return True


def get_bouquet_discount(bouquet, settings) -> Optional[DiscountInfo]:
    # Event Space is booked externally and tiers own its displayed pricing.
    # It must never inherit checkout-oriented catalog discounts.
    catalog_type = _catalog_type_value(bouquet)
    if catalog_type == "EVENT_SPACE":
        return None
    if bouquet.discount_percent > 0:
        return DiscountInfo(
            percent=bouquet.discount_percent,
            note=bouquet.discount_note or "Discount",
            source="bouquet",
        )

    if _matches_category(bouquet, settings):
        return DiscountInfo(
            percent=settings.category_discount_percent,
            note=settings.category_discount_note or "Discount",
            source="category",
        )

    if settings.global_discount_percent > 0:
        return DiscountInfo(
            percent=settings.global_discount_percent,
            note=settings.global_discount_note or "Discount",
            source="global",
        )

    return None


def get_bouquet_pricing(bouquet, settings) -> dict:
    discount = get_bouquet_discount(bouquet, settings)
    base_price = int(getattr(bouquet, "price_cents", 0) or 0)
    final_price = (
        apply_percent_discount(base_price, discount.percent)
        if discount
        else base_price
    )
    return {
        "original_price_cents": base_price,
        "final_price_cents": final_price,
        "discount": discount,
    }


def get_cart_item_discount(item, settings) -> Optional[DiscountInfo]:
    if (item.get("bouquet_discount_percent") or 0) > 0:
        return DiscountInfo(
            percent=item.get("bouquet_discount_percent") or 0,
            note=item.get("bouquet_discount_note") or "Discount",
            source="bouquet",
        )

    class Obj:
        pass

    bouquet = Obj()
    bouquet.flower_type = item.get("flower_type")
    bouquet.is_mixed = bool(item.get("is_mixed"))
    bouquet.bouquet_type = item.get("bouquet_type")
    bouquet.colors = item.get("colors") or ""
    bouquet.price_cents = item.get("base_price_cents") or 0
    bouquet.discount_percent = 0
    bouquet.discount_note = None
    # Cart reconstruction is retained for compatibility with older callers.
    # Keep its catalog type so flower-only category rules cannot leak onto a
    # neutralized gift or balloon payload.
    bouquet.catalog_type = item.get("catalog_type") or item.get("catalogType") or "FLOWERS"
    return get_bouquet_discount(bouquet, settings)
