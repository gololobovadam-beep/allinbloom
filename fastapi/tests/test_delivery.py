from __future__ import annotations

import os
import logging
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from app.services import delivery


class _FakeResponse:
    def __init__(self, *, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        self._response = _FakeResponse(
            status_code=200,
            payload={
                "status": "OK",
                "rows": [
                    {
                        "elements": [
                            {
                                "status": "OK",
                                "distance": {"value": 40234, "text": "25 mi"},
                            }
                        ]
                    }
                ],
            },
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, params):  # noqa: ARG002
        return self._response


class _FarDistanceAsyncClient(_FakeAsyncClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._response = _FakeResponse(
            status_code=200,
            payload={
                "status": "OK",
                "rows": [
                    {
                        "elements": [
                            {
                                "status": "OK",
                                "distance": {"value": 56327, "text": "35 mi"},
                            }
                        ]
                    }
                ],
            },
        )


class DeliveryValidationTests(unittest.TestCase):
    def test_validate_address_format(self):
        self.assertEqual(
            delivery._validate_address_format("  "),
            "Address is too short. Please provide a complete address.",
        )
        self.assertEqual(
            delivery._validate_address_format("Main Street, Chicago, IL"),
            "Please include a street number.",
        )
        self.assertEqual(
            delivery._validate_address_format("123 Main Street Chicago IL"),
            "Please provide a complete address with city and state (e.g., 123 Main St, Chicago, IL).",
        )
        self.assertIsNone(delivery._validate_address_format("123 Main St, Chicago, IL"))

    def test_get_delivery_fee_cents_uses_new_distance_pricing(self):
        self.assertEqual(delivery.get_delivery_fee_cents(0), 0)
        self.assertEqual(delivery.get_delivery_fee_cents(10), 0)
        self.assertEqual(delivery.get_delivery_fee_cents(10.5), 2000)
        self.assertEqual(delivery.get_delivery_fee_cents(11.7), 2200)
        self.assertEqual(delivery.get_delivery_fee_cents(12.4), 2400)
        self.assertEqual(delivery.get_delivery_fee_cents(29.99), 5800)
        self.assertIsNone(delivery.get_delivery_fee_cents(30))

    def test_build_delivery_quote_log_context_uses_safe_diagnostics(self):
        quote = delivery.DeliveryQuote(
            ok=False,
            error="Address not found. Please check and try again.",
            stage="geocode_validation",
            code="address_not_found",
            provider="google_maps",
            provider_status="ZERO_RESULTS",
        )
        context = delivery.build_delivery_quote_log_context("999 Missing St, Chicago, IL", quote)

        self.assertEqual(context["delivery_stage"], "geocode_validation")
        self.assertEqual(context["delivery_code"], "address_not_found")
        self.assertEqual(context["delivery_provider_status"], "ZERO_RESULTS")
        self.assertEqual(context["address_length"], len("999 Missing St, Chicago, IL"))
        self.assertNotIn("address", context)

    def test_delivery_quote_failure_level_distinguishes_technical_failures(self):
        technical = delivery.DeliveryQuote(
            ok=False,
            error="Delivery is not configured.",
            stage="configuration",
            code="delivery_not_configured",
        )
        user_input = delivery.DeliveryQuote(
            ok=False,
            error="Please include a street number.",
            stage="input_validation",
            code="address_missing_street_number",
        )

        self.assertEqual(delivery.delivery_quote_failure_level(technical), logging.ERROR)
        self.assertEqual(delivery.delivery_quote_failure_level(user_input), logging.WARNING)


class DeliveryQuoteTests(unittest.IsolatedAsyncioTestCase):
    async def test_delivery_quote_requires_address(self):
        quote = await delivery.get_delivery_quote("   ")
        self.assertFalse(quote.ok)
        self.assertEqual(quote.error, "Delivery address is required.")
        self.assertEqual(quote.stage, "input_validation")
        self.assertEqual(quote.code, "delivery_address_missing")

    async def test_delivery_quote_requires_google_maps_configuration(self):
        with patch.object(delivery.settings, "google_maps_api_key", None):
            quote = await delivery.get_delivery_quote("123 Main St, Chicago, IL")
        self.assertFalse(quote.ok)
        self.assertEqual(quote.error, "Delivery is not configured.")
        self.assertEqual(quote.stage, "configuration")
        self.assertEqual(quote.code, "delivery_not_configured")

    async def test_delivery_quote_success_path(self):
        with patch.object(delivery.settings, "google_maps_api_key", "test-key"), patch.object(
            delivery.settings, "delivery_base_address", "1995 Hicks Rd, Rolling Meadows, IL"
        ), patch(
            "app.services.delivery._validate_and_geocode",
            AsyncMock(
                return_value=delivery.DeliveryValidationResult(
                    ok=True,
                    formatted_address="123 Main St, Chicago, IL",
                    provider_status="OK",
                )
            ),
        ), patch("app.services.delivery.httpx.AsyncClient", _FakeAsyncClient):
            quote = await delivery.get_delivery_quote("123 Main St, Chicago, IL")

        self.assertTrue(quote.ok)
        self.assertEqual(quote.fee_cents, 5000)
        self.assertEqual(quote.distance_text, "25 mi")
        self.assertEqual(quote.formatted_address, "123 Main St, Chicago, IL")
        self.assertEqual(quote.code, "delivery_quote_ok")

    async def test_delivery_quote_rejects_addresses_outside_radius(self):
        with patch.object(delivery.settings, "google_maps_api_key", "test-key"), patch.object(
            delivery.settings, "delivery_base_address", "1995 Hicks Rd, Rolling Meadows, IL"
        ), patch(
            "app.services.delivery._validate_and_geocode",
            AsyncMock(
                return_value=delivery.DeliveryValidationResult(
                    ok=True,
                    formatted_address="500 Faraway Ave, Rockford, IL",
                    provider_status="OK",
                )
            ),
        ), patch("app.services.delivery.httpx.AsyncClient", _FarDistanceAsyncClient):
            quote = await delivery.get_delivery_quote("500 Faraway Ave, Rockford, IL")

        self.assertFalse(quote.ok)
        self.assertIsNotNone(quote.error)
        self.assertIn("within 29.99 miles", quote.error)
        self.assertEqual(quote.stage, "delivery_radius")
        self.assertEqual(quote.code, "delivery_out_of_range")

    async def test_delivery_quote_surfaces_geocode_diagnostics(self):
        with patch.object(delivery.settings, "google_maps_api_key", "test-key"), patch(
            "app.services.delivery._validate_and_geocode",
            AsyncMock(
                return_value=delivery.DeliveryValidationResult(
                    ok=False,
                    error="Address not found. Please check and try again.",
                    code="address_not_found",
                    provider_status="ZERO_RESULTS",
                )
            ),
        ):
            quote = await delivery.get_delivery_quote("999 Missing St, Chicago, IL")

        self.assertFalse(quote.ok)
        self.assertEqual(quote.stage, "geocode_validation")
        self.assertEqual(quote.code, "address_not_found")
        self.assertEqual(quote.provider_status, "ZERO_RESULTS")


if __name__ == "__main__":
    unittest.main()
