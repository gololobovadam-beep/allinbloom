from __future__ import annotations

import os
from types import SimpleNamespace
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from app.services.pricing import (
    apply_percent_discount,
    clamp_percent,
    get_bouquet_discount,
    get_bouquet_pricing,
    get_cart_item_discount,
)


def make_settings(**overrides):
    defaults = {
        "global_discount_percent": 0,
        "global_discount_note": None,
        "category_discount_percent": 0,
        "category_discount_note": None,
        "category_flower_type": None,
        "category_mixed": None,
        "category_color": None,
        "category_min_price_cents": None,
        "category_max_price_cents": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_bouquet(**overrides):
    defaults = {
        "price_cents": 10000,
        "discount_percent": 0,
        "discount_note": None,
        "flower_type": "ROSE",
        "is_mixed": False,
        "bouquet_type": "MONO",
        "colors": "Red,White",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class PricingTests(unittest.TestCase):
    def test_clamp_percent_rounds_and_clamps(self):
        self.assertEqual(clamp_percent(-4), 0)
        self.assertEqual(clamp_percent(12.6), 13)
        self.assertEqual(clamp_percent(120), 90)

    def test_apply_percent_discount_handles_boundaries(self):
        self.assertEqual(apply_percent_discount(10000, 25), 7500)
        self.assertEqual(apply_percent_discount(999, 33), 669)
        self.assertEqual(apply_percent_discount(10000, 200), 1000)
        self.assertEqual(apply_percent_discount(10000, -5), 10000)

    def test_discount_priority_bouquet_then_category_then_global(self):
        bouquet = make_bouquet(discount_percent=35, discount_note="VIP")
        settings = make_settings(
            category_discount_percent=20,
            category_flower_type="ROSE",
            global_discount_percent=5,
        )
        discount = get_bouquet_discount(bouquet, settings)
        self.assertIsNotNone(discount)
        self.assertEqual(discount.percent, 35)
        self.assertEqual(discount.note, "VIP")
        self.assertEqual(discount.source, "bouquet")

    def test_category_discount_requires_filters(self):
        bouquet = make_bouquet()
        settings = make_settings(
            category_discount_percent=20,
            global_discount_percent=7,
            global_discount_note="Global",
        )
        discount = get_bouquet_discount(bouquet, settings)
        self.assertIsNotNone(discount)
        self.assertEqual(discount.percent, 7)
        self.assertEqual(discount.source, "global")

    def test_category_discount_matches_multiple_criteria(self):
        bouquet = make_bouquet()
        settings = make_settings(
            category_discount_percent=15,
            category_discount_note="Category",
            category_flower_type="ROSE",
            category_mixed="mono",
            category_color="red",
            category_min_price_cents=9000,
            category_max_price_cents=11000,
        )
        discount = get_bouquet_discount(bouquet, settings)
        self.assertIsNotNone(discount)
        self.assertEqual(discount.percent, 15)
        self.assertEqual(discount.note, "Category")
        self.assertEqual(discount.source, "category")

    def test_category_discount_season_matches_only_season_bouquets(self):
        season_bouquet = make_bouquet(bouquet_type="SEASON", is_mixed=False)
        season_settings = make_settings(
            category_discount_percent=17,
            category_mixed="season",
        )
        season_discount = get_bouquet_discount(season_bouquet, season_settings)
        self.assertIsNotNone(season_discount)
        self.assertEqual(season_discount.percent, 17)
        self.assertEqual(season_discount.source, "category")

        mono_settings = make_settings(
            category_discount_percent=17,
            category_mixed="mono",
        )
        mono_discount = get_bouquet_discount(season_bouquet, mono_settings)
        self.assertIsNone(mono_discount)

    def test_get_bouquet_pricing_calculates_final_price(self):
        bouquet = make_bouquet()
        settings = make_settings(global_discount_percent=10, global_discount_note="Weekend")
        pricing = get_bouquet_pricing(bouquet, settings)
        self.assertEqual(pricing["original_price_cents"], 10000)
        self.assertEqual(pricing["final_price_cents"], 9000)
        self.assertEqual(pricing["discount"].source, "global")

    def test_get_cart_item_discount_uses_item_discount_first(self):
        settings = make_settings(
            category_discount_percent=30,
            category_flower_type="ROSE",
            global_discount_percent=5,
        )
        discount = get_cart_item_discount(
            {
                "base_price_cents": 12000,
                "bouquet_discount_percent": 12,
                "bouquet_discount_note": "Item promo",
            },
            settings,
        )
        self.assertIsNotNone(discount)
        self.assertEqual(discount.percent, 12)
        self.assertEqual(discount.note, "Item promo")
        self.assertEqual(discount.source, "bouquet")

    def test_get_cart_item_discount_can_match_category(self):
        settings = make_settings(
            category_discount_percent=11,
            category_flower_type="ROSE",
            category_mixed="mono",
            category_color="red",
        )
        discount = get_cart_item_discount(
            {
                "base_price_cents": 10000,
                "flower_type": "ROSE",
                "is_mixed": False,
                "colors": "Deep RED",
            },
            settings,
        )
        self.assertIsNotNone(discount)
        self.assertEqual(discount.percent, 11)
        self.assertEqual(discount.source, "category")

    def test_get_cart_item_discount_never_applies_flower_category_to_gifts(self):
        settings = make_settings(
            category_discount_percent=11,
            category_flower_type="ROSE",
            category_mixed="mono",
            category_color="red",
        )
        discount = get_cart_item_discount(
            {
                "base_price_cents": 10000,
                "catalog_type": "GIFTS",
                # These values mirror the neutral legacy product fields used
                # by the shared product table and must not qualify a gift.
                "flower_type": "ROSE",
                "is_mixed": False,
                "colors": "Deep RED",
            },
            settings,
        )
        self.assertIsNone(discount)

    def test_get_cart_item_discount_can_match_season_category(self):
        settings = make_settings(
            category_discount_percent=11,
            category_mixed="season",
        )
        discount = get_cart_item_discount(
            {
                "base_price_cents": 10000,
                "flower_type": "ROSE",
                "is_mixed": False,
                "bouquet_type": "SEASON",
                "colors": "Deep RED",
            },
            settings,
        )
        self.assertIsNotNone(discount)
        self.assertEqual(discount.percent, 11)
        self.assertEqual(discount.source, "category")


if __name__ == "__main__":
    unittest.main()
