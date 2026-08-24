from __future__ import annotations

import asyncio
import os
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

# Importing the package registers every model with Base metadata, including
# the outbox and financial ledger introduced by the payment migration.
import app.models  # noqa: F401
from app.api.routes.paypal import _resolve_paypal_refund_id_from_event
from app.api.routes.stripe_webhook import (
    _resolve_order_for_stripe_charge,
    _status_after_dispute_won,
)
from app.core.config import settings
from app.core.database import Base
from app.models.enums import OrderStatus
from app.models.notification_outbox import NotificationOutbox
from app.models.order import Order
from app.models.payment_ledger_entry import PaymentLedgerEntry
from app.models.webhook_event import WebhookEvent
from app.services.orders import resolve_order_status_from_session
from app.services.payment_ledger import apply_provider_refund_once
from app.services.payment_notifications import mark_order_paid
from app.services.webhook_events import (
    claim_webhook_event,
    mark_webhook_event_processed,
    release_webhook_event_claim,
)


class PaymentReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _order(self, *, total_cents: int = 10_000, status=OrderStatus.PENDING) -> Order:
        order = Order(
            email="buyer@example.com",
            total_cents=total_cents,
            currency="USD",
            status=status,
        )
        self.db.add(order)
        self.db.commit()
        return order

    def test_paid_transition_enqueues_two_durable_notifications_once(self):
        order = self._order()

        self.assertTrue(mark_order_paid(self.db, order, stripe_payment_intent_id="pi_1"))
        self.assertFalse(mark_order_paid(self.db, order, stripe_payment_intent_id="pi_1"))

        entries = self.db.execute(
            select(NotificationOutbox).where(NotificationOutbox.order_id == order.id)
        ).scalars().all()
        self.assertEqual(order.status, OrderStatus.PAID)
        self.assertEqual(len(entries), 2)
        self.assertEqual({entry.status for entry in entries}, {"PENDING"})

    def test_outbox_dispatch_claims_and_sends_each_confirmation_once(self):
        from app.services.payment_notifications import dispatch_pending_order_notifications

        order = self._order()
        self.assertTrue(mark_order_paid(self.db, order))
        with patch(
            "app.services.payment_notifications.send_admin_order_email", new=AsyncMock()
        ) as send_admin, patch(
            "app.services.payment_notifications.send_customer_order_email", new=AsyncMock()
        ) as send_customer:
            delivered = asyncio.run(
                dispatch_pending_order_notifications(self.db, limit=10)
            )
            delivered_again = asyncio.run(
                dispatch_pending_order_notifications(self.db, limit=10)
            )

        entries = self.db.execute(
            select(NotificationOutbox).where(NotificationOutbox.order_id == order.id)
        ).scalars().all()
        self.assertEqual(delivered, 2)
        self.assertEqual(delivered_again, 0)
        self.assertEqual(send_admin.await_count, 1)
        self.assertEqual(send_customer.await_count, 1)
        self.assertEqual({entry.status for entry in entries}, {"SENT"})

    def test_outbox_retries_when_email_provider_is_not_configured(self):
        from app.services.payment_notifications import dispatch_pending_order_notifications

        order = self._order()
        self.assertTrue(mark_order_paid(self.db, order))
        with patch.object(settings, "resend_api_key", None):
            delivered = asyncio.run(
                dispatch_pending_order_notifications(self.db, limit=10)
            )

        entries = self.db.execute(
            select(NotificationOutbox).where(NotificationOutbox.order_id == order.id)
        ).scalars().all()
        self.assertEqual(delivered, 0)
        self.assertEqual({entry.status for entry in entries}, {"RETRY"})
        self.assertEqual({entry.attempt_count for entry in entries}, {1})

    def test_refund_ledger_deduplicates_two_paypal_notifications_for_one_refund(self):
        order = self._order(status=OrderStatus.PAID)

        first = apply_provider_refund_once(
            self.db,
            order=order,
            provider="paypal",
            external_reference="refund:REFUND-50",
            amount_cents=5_000,
            currency="USD",
            source_event_id="event-capture-refunded",
        )
        self.db.commit()
        duplicate = apply_provider_refund_once(
            self.db,
            order=order,
            provider="paypal",
            external_reference="refund:REFUND-50",
            amount_cents=5_000,
            currency="USD",
            source_event_id="event-refund-completed",
        )
        self.db.commit()
        self.db.refresh(order)

        ledger = self.db.execute(
            select(PaymentLedgerEntry).where(PaymentLedgerEntry.order_id == order.id)
        ).scalars().all()
        self.assertTrue(first.state_updated)
        self.assertFalse(duplicate.state_updated)
        self.assertEqual(duplicate.reason, "duplicate")
        self.assertEqual(order.refunded_cents, 5_000)
        self.assertEqual(order.status, OrderStatus.PARTIALLY_REFUNDED)
        self.assertEqual(len(ledger), 1)

    def test_webhook_claim_does_not_acknowledge_inflight_event_and_releases_retry(self):
        self.assertTrue(claim_webhook_event(self.db, provider="stripe", event_id="evt_1"))
        self.assertFalse(claim_webhook_event(self.db, provider="stripe", event_id="evt_1"))

        release_webhook_event_claim(self.db, provider="stripe", event_id="evt_1")
        self.assertTrue(claim_webhook_event(self.db, provider="stripe", event_id="evt_1"))
        mark_webhook_event_processed(self.db, provider="stripe", event_id="evt_1")
        self.assertFalse(claim_webhook_event(self.db, provider="stripe", event_id="evt_1"))
        stored = self.db.execute(select(WebhookEvent)).scalar_one()
        self.assertEqual(stored.status, "PROCESSED")

    def test_open_checkout_payment_intent_failure_remains_retryable(self):
        order = self._order()
        order.stripe_session_id = "cs_open"
        self.db.commit()
        session = {
            "id": "cs_open",
            "metadata": {"orderId": order.id},
            "status": "open",
            "payment_status": "unpaid",
            "amount_total": order.total_cents,
            "currency": "usd",
            "payment_intent": {"status": "requires_payment_method"},
        }

        self.assertIsNone(resolve_order_status_from_session(order, session))
        self.assertEqual(order.status, OrderStatus.PENDING)

    def test_stripe_charge_fallback_links_order_from_payment_intent_metadata(self):
        order = self._order()
        charge = {
            "id": "ch_early",
            "payment_intent": "pi_early",
            "amount": order.total_cents,
            "currency": "usd",
            "metadata": {},
        }
        payment_intent = {"id": "pi_early", "metadata": {"orderId": order.id}}

        with patch(
            "app.api.routes.stripe_webhook.stripe.Charge.retrieve", return_value=charge
        ), patch(
            "app.api.routes.stripe_webhook.stripe.PaymentIntent.retrieve",
            return_value=payment_intent,
        ):
            resolved = asyncio.run(
                _resolve_order_for_stripe_charge(self.db, charge_id="ch_early")
            )

        self.assertIsNotNone(resolved)
        self.db.refresh(order)
        self.assertEqual(order.stripe_charge_id, "ch_early")
        self.assertEqual(order.stripe_payment_intent_id, "pi_early")

    def test_paypal_refund_reference_never_uses_capture_id_as_refund_id(self):
        capture_event = {
            "resource": {
                "id": "CAPTURE-1",
                "supplementary_data": {"related_ids": {"capture_id": "CAPTURE-1"}},
            }
        }
        refund_event = {"resource": {"id": "REFUND-1"}}
        correlated_capture_event = {
            "resource": {
                "id": "CAPTURE-1",
                "supplementary_data": {"related_ids": {"refund_id": "REFUND-1"}},
            }
        }

        self.assertIsNone(
            _resolve_paypal_refund_id_from_event(
                capture_event, "PAYMENT.CAPTURE.REFUNDED"
            )
        )
        self.assertEqual(
            _resolve_paypal_refund_id_from_event(
                refund_event, "PAYMENT.REFUND.COMPLETED"
            ),
            "REFUND-1",
        )
        self.assertEqual(
            _resolve_paypal_refund_id_from_event(
                correlated_capture_event, "PAYMENT.CAPTURE.REFUNDED"
            ),
            "REFUND-1",
        )

    def test_dispute_win_restores_refund_state_not_plain_paid(self):
        order = self._order(status=OrderStatus.DISPUTED)
        order.refunded_cents = 5_000
        self.assertEqual(_status_after_dispute_won(order), OrderStatus.PARTIALLY_REFUNDED)
        order.refunded_cents = order.total_cents
        self.assertEqual(_status_after_dispute_won(order), OrderStatus.REFUNDED)

    def test_refund_during_dispute_keeps_dispute_state_until_resolved(self):
        order = self._order(status=OrderStatus.DISPUTED)
        result = apply_provider_refund_once(
            self.db,
            order=order,
            provider="paypal",
            external_reference="refund:DISPUTE-REFUND",
            amount_cents=1_000,
            currency="USD",
        )
        self.db.commit()
        self.db.refresh(order)
        self.assertTrue(result.state_updated)
        self.assertEqual(order.refunded_cents, 1_000)
        self.assertEqual(order.status, OrderStatus.DISPUTED)


if __name__ == "__main__":
    unittest.main()
