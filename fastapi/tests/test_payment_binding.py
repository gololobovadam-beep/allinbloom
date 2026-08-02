from __future__ import annotations

import os
from types import SimpleNamespace
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from app.models.enums import OrderStatus
from app.schemas.checkout import CheckoutItemIn, CheckoutRequest
from app.services.orders import (
    resolve_order_status_from_paypal_order,
    resolve_order_status_from_session,
)
from pydantic import ValidationError


def make_order(**overrides):
    values = {
        "id": "order-1",
        "stripe_session_id": "cs_1",
        "total_cents": 12900,
        "currency": "USD",
        "created_at": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def paypal_payload(**overrides):
    values = {
        "status": "COMPLETED",
        "purchase_units": [
            {
                "custom_id": "order-1",
                "amount": {"value": "129.00", "currency_code": "USD"},
                "payments": {
                    "captures": [{"id": "capture-1", "status": "COMPLETED"}]
                },
            }
        ],
    }
    values.update(overrides)
    return values


class PaymentBindingTests(unittest.TestCase):
    def test_stripe_paid_status_requires_exact_order_and_session_bindings(self):
        order = make_order()
        session = {
            "id": "cs_1",
            "metadata": {"orderId": "order-1"},
            "status": "complete",
            "payment_status": "paid",
            "amount_total": 12900,
            "currency": "usd",
        }
        self.assertEqual(resolve_order_status_from_session(order, session), OrderStatus.PAID)

        self.assertIsNone(
            resolve_order_status_from_session(order, {**session, "id": "cs_other"})
        )
        self.assertIsNone(
            resolve_order_status_from_session(
                order, {**session, "metadata": {"orderId": "other-order"}}
            )
        )
        self.assertIsNone(resolve_order_status_from_session(order, {**session, "currency": ""}))

    def test_paypal_paid_status_requires_exact_custom_id_amount_and_currency(self):
        order = make_order()
        status, capture_id = resolve_order_status_from_paypal_order(order, paypal_payload())
        self.assertEqual(status, OrderStatus.PAID)
        self.assertEqual(capture_id, "capture-1")

        wrong_custom = paypal_payload(
            purchase_units=[
                {
                    "custom_id": "other-order",
                    "amount": {"value": "129.00", "currency_code": "USD"},
                }
            ]
        )
        self.assertEqual(resolve_order_status_from_paypal_order(order, wrong_custom), (None, None))
        wrong_amount = paypal_payload(
            purchase_units=[
                {
                    "custom_id": "order-1",
                    "amount": {"value": "1.00", "currency_code": "USD"},
                }
            ]
        )
        self.assertEqual(resolve_order_status_from_paypal_order(order, wrong_amount), (None, None))

    def test_checkout_schema_bounds_cart_size_and_quantity(self):
        with self.assertRaises(ValidationError):
            CheckoutItemIn(id="bouquet-1", quantity=0)
        with self.assertRaises(ValidationError):
            CheckoutRequest(
                items=[CheckoutItemIn(id=f"bouquet-{index}", quantity=1) for index in range(26)]
            )


if __name__ == "__main__":
    unittest.main()
