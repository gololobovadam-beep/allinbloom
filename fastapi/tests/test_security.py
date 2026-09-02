from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import os
import re
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from fastapi import Response
from app.core import security
from app.core.config import settings
from app.api.routes.auth import _build_auth_response, _google_oauth_error_response
from app.models.enums import Role
from app.models.user import User


class SecurityTests(unittest.TestCase):
    def test_generate_and_verify_otp(self):
        generated = security.generate_otp()
        code = generated["code"]
        salt = generated["salt"]
        code_hash = generated["hash"]
        expires_at = generated["expires_at"]

        self.assertRegex(str(code), r"^\d{6}$")
        self.assertRegex(str(salt), r"^[0-9a-f]{32}$")
        self.assertTrue(re.fullmatch(r"[0-9a-f]{64}", str(code_hash)))
        self.assertIsInstance(expires_at, datetime)
        self.assertGreater(expires_at, datetime.now(timezone.utc))
        self.assertTrue(security.verify_otp(str(code), str(salt), str(code_hash)))
        self.assertFalse(security.verify_otp("000000", str(salt), str(code_hash)))

    def test_access_and_refresh_token_roundtrip(self):
        with patch.object(
            settings, "auth_secret", "unit-test-secret-with-at-least-32-characters"
        ), patch.object(
            settings, "environment", "test"
        ):
            access = security.create_access_token({"sub": "user-1"}, expires_minutes=5)
            payload = security.decode_access_token(access)
            self.assertEqual(payload["sub"], "user-1")
            self.assertEqual(payload["type"], "access")

            refresh = security.create_refresh_token({"sub": "user-1"}, expires_days=3)
            refresh_payload = security.decode_refresh_token(refresh)
            self.assertEqual(refresh_payload["sub"], "user-1")
            self.assertEqual(refresh_payload["type"], "refresh")

            with self.assertRaises(ValueError):
                security.decode_access_token(refresh)

    def test_signing_in_on_another_device_keeps_existing_session_version(self):
        user = User(
            id="user-1",
            email="customer@example.com",
            name="Customer",
            role=Role.CUSTOMER,
            auth_version=7,
        )
        db = Mock()

        with patch.object(
            settings, "auth_secret", "unit-test-secret-with-at-least-32-characters"
        ), patch.object(settings, "environment", "test"):
            first_response = Response()
            _build_auth_response(first_response, user, db)
            second_response = Response()
            _build_auth_response(second_response, user, db)

        self.assertEqual(user.auth_version, 7)
        db.commit.assert_not_called()

    def test_checkout_access_token_is_bound_to_one_order_without_email_data(self):
        with patch.object(
            settings, "auth_secret", "unit-test-secret-with-at-least-32-characters"
        ), patch.object(
            settings, "environment", "test"
        ):
            token = security.create_checkout_access_token(
                order_id="order-123", expires_hours=2
            )
            payload = security.decode_checkout_access_token(token)

        self.assertEqual(payload, {"order_id": "order-123"})
        self.assertEqual(
            security.checkout_access_cookie_name("order-123"), "aib_checkout_order-123"
        )

    def test_checkout_access_token_validates_required_order_id(self):
        with patch.object(
            settings, "auth_secret", "unit-test-secret-with-at-least-32-characters"
        ), patch.object(
            settings, "environment", "test"
        ):
            missing_order = security._encode_token(
                {},
                timedelta(hours=1),
                "checkout_access",
            )

            with self.assertRaisesRegex(ValueError, "Invalid checkout access token"):
                security.decode_checkout_access_token(missing_order)
            with self.assertRaises(ValueError):
                security.checkout_access_cookie_name("unsafe order id")

    def test_google_oauth_state_requires_matching_signed_cookie_value(self):
        with patch.object(
            settings, "auth_secret", "unit-test-secret-with-at-least-32-characters"
        ), patch.object(
            settings, "environment", "test"
        ):
            state = security.create_google_oauth_state_token()
            self.assertTrue(
                security.validate_google_oauth_state_token(
                    received_state=state,
                    expected_state=state,
                )
            )
            self.assertFalse(
                security.validate_google_oauth_state_token(
                    received_state=f"{state}tampered",
                    expected_state=state,
                )
            )
            self.assertFalse(
                security.validate_google_oauth_state_token(
                    received_state=state,
                    expected_state=None,
                )
            )

    def test_google_oauth_error_consumes_state_cookie(self):
        with patch.object(settings, "environment", "test"):
            response = _google_oauth_error_response(400, "Invalid Google sign-in state.")

        set_cookie = response.headers.get("set-cookie", "")
        self.assertIn("aib_google_oauth_state=", set_cookie)
        self.assertIn("Max-Age=0", set_cookie)
        self.assertIn("Path=/api/auth/google", set_cookie)

    def test_token_encoding_requires_secret_in_production(self):
        with patch.object(settings, "auth_secret", ""), patch.object(
            settings, "environment", "production"
        ):
            with self.assertRaises(RuntimeError):
                security.create_access_token({"sub": "user-1"}, expires_minutes=1)

    def test_runtime_config_rejects_missing_environment_and_weak_secret(self):
        with patch.object(settings, "environment", ""), patch.object(
            settings, "auth_secret", "x" * 32
        ):
            with self.assertRaisesRegex(RuntimeError, "ENVIRONMENT"):
                settings.validate_runtime_configuration()

        with patch.object(settings, "environment", "production"), patch.object(
            settings, "auth_secret", "replace-with-a-long-random-string"
        ), patch.object(settings, "site_url", "https://example.com"):
            with self.assertRaisesRegex(RuntimeError, "AUTH_SECRET"):
                settings.validate_runtime_configuration()

    def test_runtime_config_requires_tls_postgresql_in_production(self):
        common = {
            "environment": "production",
            "auth_secret": "test-secret-1234567890-ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "site_url": "https://example.com",
            "paypal_env": "sandbox",
            "stripe_secret_key": None,
            "stripe_webhook_secret": None,
            "paypal_client_id": None,
            "paypal_client_secret": None,
            "paypal_webhook_id": None,
        }

        def validate(database_url: str) -> None:
            with ExitStack() as stack:
                stack.enter_context(patch.object(settings, "database_url", database_url))
                for key, value in common.items():
                    stack.enter_context(patch.object(settings, key, value))
                settings.validate_runtime_configuration()

        with self.assertRaisesRegex(RuntimeError, "sslmode"):
            validate("postgresql+psycopg://user:pass@db/app")

        validate("postgresql+psycopg://user:pass@db/app?sslmode=require")

    def test_runtime_config_requires_email_delivery_for_production_payments(self):
        values = {
            "environment": "production",
            "auth_secret": "test-secret-1234567890-ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "site_url": "https://example.com",
            "database_url": "postgresql+psycopg://user:pass@db/app?sslmode=require",
            "paypal_env": "live",
            "stripe_secret_key": "sk_live_123",
            "stripe_webhook_secret": "whsec_123",
            "paypal_client_id": None,
            "paypal_client_secret": None,
            "paypal_webhook_id": None,
            "resend_api_key": None,
        }
        with ExitStack() as stack:
            for key, value in values.items():
                stack.enter_context(patch.object(settings, key, value))
            with self.assertRaisesRegex(RuntimeError, "RESEND_API_KEY"):
                settings.validate_runtime_configuration()


if __name__ == "__main__":
    unittest.main()
