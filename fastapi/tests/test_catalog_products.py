from __future__ import annotations

import os
import unittest
from types import SimpleNamespace

from fastapi import HTTPException

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from app.models.enums import CatalogType, FlowerType
from app.schemas.bouquet import BouquetCreate, BouquetOut
from app.services.catalog_products import (
    normalize_gallery_images,
    normalize_youtube_url,
    replace_bouquet_gallery_images,
    replace_event_tiers,
    replace_home_gallery_images,
)


class _Tier:
    id = "tier-1"
    price_cents = 12500
    title = "Private event"
    description = "Private evening event"


class _Gift:
    id = "gift-1"
    catalog_type = "GIFTS"
    category_id = None
    category = None
    name = "Gift box"
    description = "A thoughtful gift"
    price_cents = 9500
    currency = "USD"
    flower_type = FlowerType.MIXED
    style = ""
    bouquet_type = "MONO"
    colors = ""
    is_mixed = False
    is_featured = False
    is_active = True
    is_sold_out = False
    allow_flower_quantity = False
    default_flower_quantity = 1
    discount_percent = 0
    discount_note = None
    video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    video_orientation = "VERTICAL"
    gallery_image_urls = ["/images/gift-1.webp", "/images/gift-2.webp"]
    event_tiers = [_Tier()]
    image = "/images/gift-1.webp"
    image_2 = None
    image_3 = None
    image_4 = None
    image_5 = None
    image_6 = None


class CatalogProductSchemaTests(unittest.TestCase):
    def test_gift_payload_accepts_camel_case_gallery_fields(self):
        payload = BouquetCreate.model_validate(
            {
                "catalogType": "GIFTS",
                "name": "Gift box",
                "description": "A thoughtful gift",
                "priceCents": 9500,
                "galleryImages": ["/images/gift-1.webp", "/images/gift-2.webp"],
            }
        )
        self.assertEqual(payload.catalog_type, CatalogType.GIFTS)
        self.assertEqual(payload.gallery_images, ["/images/gift-1.webp", "/images/gift-2.webp"])

    def test_catalog_currency_is_normalized_to_usd_and_rejects_other_values(self):
        payload = BouquetCreate.model_validate(
            {
                "catalogType": "GIFTS",
                "name": "Gift box",
                "description": "A thoughtful gift",
                "priceCents": 9500,
                "image": "/images/gift-1.webp",
                "currency": " usd ",
            }
        )
        self.assertEqual(payload.currency, "USD")
        with self.assertRaises(ValueError):
            BouquetCreate.model_validate(
                {
                    "catalogType": "GIFTS",
                    "name": "Gift box",
                    "description": "A thoughtful gift",
                    "priceCents": 9500,
                    "image": "/images/gift-1.webp",
                    "currency": "EUR",
                }
            )

    def test_event_payload_uses_tiers_and_zero_legacy_price_when_omitted(self):
        payload = BouquetCreate.model_validate(
            {
                "catalogType": "EVENT_SPACE",
                "name": "Event space",
                "description": "Private events",
                "image": "/images/event.webp",
                "tiers": [
                    {
                        "priceCents": 12000,
                        "title": "Small event",
                        "description": "Small event",
                    }
                ],
            }
        )
        self.assertEqual(payload.price_cents, 0)
        self.assertEqual(payload.tiers[0].title, "Small event")
        self.assertEqual(payload.tiers[0].price_cents, 12000)
        no_tiers_payload = BouquetCreate.model_validate(
            {
                "catalogType": "EVENT_SPACE",
                "name": "Event space",
                "description": "Private events",
                "image": "/images/event.webp",
            }
        )
        self.assertEqual(no_tiers_payload.price_cents, 0)
        self.assertIsNone(no_tiers_payload.tiers)
        with self.assertRaises(ValueError):
            BouquetCreate.model_validate(
                {
                    "catalogType": "EVENT_SPACE",
                    "name": "Event space",
                    "description": "Private events",
                    "image": "/images/event.webp",
                    "priceCents": 1,
                    "tiers": [{"priceCents": 12000, "description": "Small event"}],
                }
            )

    def test_flower_payload_requires_flower_data(self):
        with self.assertRaises(ValueError):
            BouquetCreate.model_validate(
                {
                    "name": "Missing flower data",
                    "description": "No flower type",
                    "priceCents": 1000,
                    "image": "/images/flower.webp",
                }
            )

    def test_normalizers_keep_relative_images_and_canonicalize_youtube(self):
        self.assertEqual(
            normalize_gallery_images([" /images/one.webp ", "/images/one.webp", "/images/two.webp"]),
            ["/images/one.webp", "/images/two.webp"],
        )
        self.assertEqual(
            normalize_youtube_url("https://youtu.be/dQw4w9WgXcQ?t=4"),
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        )
        with self.assertRaises(HTTPException):
            normalize_youtube_url("https://example.com/video")

    def test_response_emits_exact_camel_case_contract(self):
        output = BouquetOut.model_validate(_Gift()).model_dump(by_alias=True)
        self.assertEqual(output["catalogType"], "GIFTS")
        self.assertEqual(output["galleryImages"], ["/images/gift-1.webp", "/images/gift-2.webp"])
        self.assertEqual(output["videoUrl"], "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertEqual(output["videoOrientation"], "VERTICAL")
        self.assertEqual(output["tiers"][0]["title"], "Private event")
        self.assertEqual(output["tiers"][0]["priceCents"], 12500)

    def test_relation_replacements_preserve_existing_position_rows(self):
        gallery_rows = [
            SimpleNamespace(url="/images/old-1.webp", position=0),
            SimpleNamespace(url="/images/old-2.webp", position=1),
        ]
        product = SimpleNamespace(
            gallery_image_rows=gallery_rows,
            image="/images/old-1.webp",
            image_2="/images/old-2.webp",
            image_3=None,
            image_4=None,
            image_5=None,
            image_6=None,
        )
        replace_bouquet_gallery_images(
            product, ["/images/new-1.webp", "/images/new-2.webp"]
        )
        self.assertIs(product.gallery_image_rows[0], gallery_rows[0])
        self.assertEqual(product.gallery_image_rows[0].url, "/images/new-1.webp")

        tier_rows = [
            SimpleNamespace(price_cents=1000, title=None, description="Old", position=0),
        ]
        product.event_tiers = tier_rows
        replace_event_tiers(
            product,
            [{"priceCents": 2500, "title": "Updated", "description": "New"}],
        )
        self.assertIs(product.event_tiers[0], tier_rows[0])
        self.assertEqual(product.event_tiers[0].price_cents, 2500)
        self.assertEqual(product.event_tiers[0].title, "Updated")
        replace_event_tiers(product, [])
        self.assertEqual(product.event_tiers, [])

        home_rows = [SimpleNamespace(url="/images/old-home.webp", position=0)]
        settings = SimpleNamespace(
            home_gallery_image_rows=home_rows,
            home_gallery_image_1="/images/old-home.webp",
            home_gallery_image_2=None,
            home_gallery_image_3=None,
            home_gallery_image_4=None,
            home_gallery_image_5=None,
            home_gallery_image_6=None,
        )
        replace_home_gallery_images(settings, ["/images/new-home.webp"])
        self.assertIs(settings.home_gallery_image_rows[0], home_rows[0])
        self.assertEqual(settings.home_gallery_image_rows[0].url, "/images/new-home.webp")


if __name__ == "__main__":
    unittest.main()
