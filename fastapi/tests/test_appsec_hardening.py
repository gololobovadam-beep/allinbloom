from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from io import BytesIO
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from fastapi import HTTPException, Response
from starlette.datastructures import Headers, UploadFile
from starlette.requests import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes.auth import OTP_MAX_VERIFY_ATTEMPTS, verify_code
from app.api.routes.checkout import _safe_checkout_event_context
from app.api.routes.reviews import (
    _is_trusted_review_image_url,
    create_review,
    list_reviews,
    public_review_limiter,
)
from app.api.routes.upload import (
    _normalized_upload_options,
    _read_and_validate_file,
    _upload_to_cloudinary,
    router as upload_router,
)
from app.core.config import settings
from app.core.database import Base
from app.core.security import generate_otp
from app.models.review import Review
from app.models.verification_code import VerificationCode
from app.schemas.auth import VerifyCodeIn
from app.schemas.review import ReviewCreatePublic


def _request(path: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "headers": [],
            "client": ("127.0.0.1", 12345),
        }
    )


class ReviewAndUploadSecurityTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        public_review_limiter._hits.clear()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_public_review_is_pending_and_rejects_attached_image(self):
        review = create_review(
            ReviewCreatePublic(
                name="Customer",
                email="customer@example.com",
                rating=5,
                text="Beautiful flowers.",
            ),
            _request("/api/reviews"),
            self.db,
        )

        stored = self.db.get(Review, review.id)
        self.assertFalse(stored.is_active)
        self.assertFalse(stored.is_read)
        self.assertIsNone(stored.image)

        with self.assertRaises(HTTPException) as raised:
            create_review(
                ReviewCreatePublic(
                    name="Customer",
                    email="customer2@example.com",
                    rating=5,
                    text="Beautiful flowers.",
                    image="/images/photo.webp",
                ),
                _request("/api/reviews"),
                self.db,
            )
        self.assertEqual(raised.exception.status_code, 400)

    def test_public_response_hides_legacy_untrusted_remote_image(self):
        review = Review(
            name="Legacy customer",
            email="legacy@example.com",
            rating=5,
            text="Legacy review.",
            image="https://attacker.invalid/track.gif",
            is_active=True,
            is_read=True,
        )
        self.db.add(review)
        self.db.commit()

        result = list_reviews(self.db)
        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0].image)

    def test_review_image_origin_is_limited_to_local_or_own_cloudinary(self):
        with patch.object(settings, "cloudinary_cloud_name", "all-in-bloom"):
            self.assertTrue(_is_trusted_review_image_url("/images/review.webp"))
            self.assertTrue(
                _is_trusted_review_image_url(
                    "https://res.cloudinary.com/all-in-bloom/image/upload/v1/review.webp"
                )
            )
            self.assertFalse(_is_trusted_review_image_url("https://example.com/photo.webp"))
            self.assertFalse(
                _is_trusted_review_image_url(
                    "https://res.cloudinary.com/another-cloud/image/upload/v1/review.webp"
                )
            )

    def test_public_review_upload_route_is_not_registered(self):
        paths = {route.path for route in upload_router.routes}
        self.assertNotIn("/api/upload/review", paths)
        self.assertIn("/api/upload", paths)

    def test_upload_options_apply_bounded_incoming_transformation(self):
        options = _normalized_upload_options(max_width=1200, max_height=900, fmt="webp")
        self.assertEqual(options["transformation"], "c_limit,w_1200,h_900,q_auto")
        self.assertEqual(options["format"], "webp")

        with self.assertRaises(HTTPException):
            _normalized_upload_options(max_width=4097, max_height=900, fmt="webp")
        with self.assertRaises(HTTPException):
            _normalized_upload_options(max_width=1200, max_height=900, fmt="gif")

    def test_upload_rejects_gif_before_sending_to_provider(self):
        upload = UploadFile(
            filename="animated.gif",
            file=BytesIO(b"GIF89a"),
            headers=Headers({"content-type": "image/gif"}),
        )
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(_read_and_validate_file(upload))
        self.assertEqual(raised.exception.status_code, 400)

    def test_upload_provider_invalid_json_is_a_safe_gateway_error(self):
        class InvalidJsonResponse:
            status_code = 200

            @staticmethod
            def json():
                raise ValueError("not JSON")

        class InvalidJsonClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

            async def post(self, *_args, **_kwargs):
                return InvalidJsonResponse()

        upload = UploadFile(
            filename="photo.webp",
            file=BytesIO(b"RIFF\x04\x00\x00\x00WEBP"),
            headers=Headers({"content-type": "image/webp"}),
        )
        with patch.object(settings, "cloudinary_cloud_name", "all-in-bloom"), patch.object(
            settings, "cloudinary_upload_preset", "restricted-server-preset"
        ), patch("app.api.routes.upload.httpx.AsyncClient", return_value=InvalidJsonClient()):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(_upload_to_cloudinary(upload, b"RIFF\x04\x00\x00\x00WEBP"))
        self.assertEqual(raised.exception.status_code, 502)


class OtpAndTelemetrySecurityTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_wrong_otp_does_not_invalidate_valid_code_until_attempt_limit(self):
        otp = generate_otp()
        record = VerificationCode(
            email="customer@example.com",
            code_hash=otp["hash"],
            salt=otp["salt"],
            expires_at=otp["expires_at"],
        )
        self.db.add(record)
        self.db.commit()
        record_id = record.id

        for expected_attempt_count in range(1, OTP_MAX_VERIFY_ATTEMPTS):
            with self.assertRaises(HTTPException) as raised:
                verify_code(
                    VerifyCodeIn(email="customer@example.com", code="000000"),
                    _request("/api/auth/verify-code"),
                    Response(),
                    self.db,
                )
            self.assertEqual(raised.exception.status_code, 400)
            stored = self.db.get(VerificationCode, record_id)
            self.assertIsNotNone(stored)
            self.assertEqual(stored.attempt_count, expected_attempt_count)

        with self.assertRaises(HTTPException):
            verify_code(
                VerifyCodeIn(email="customer@example.com", code="000000"),
                _request("/api/auth/verify-code"),
                Response(),
                self.db,
            )
        self.assertIsNone(self.db.get(VerificationCode, record_id))

    def test_otp_schema_rejects_non_numeric_code(self):
        with self.assertRaises(Exception):
            VerifyCodeIn(email="customer@example.com", code="abcdef")

    def test_checkout_telemetry_drops_card_and_personal_data(self):
        context = _safe_checkout_event_context(
            "browser_redirect_started",
            {
                "target": "provider_redirect",
                "cardNumber": "4242424242424242",
                "cvc": "123",
                "email": "customer@example.com",
                "deliveryAddress": "123 Main St",
            },
        )
        self.assertEqual(context, {"target": "provider_redirect"})
        self.assertEqual(
            _safe_checkout_event_context(
                "browser_success_returned",
                {"hasPaypalToken": True, "paymentToken": "secret"},
            ),
            {"hasPaypalToken": True},
        )


if __name__ == "__main__":
    unittest.main()
