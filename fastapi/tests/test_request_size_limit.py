from __future__ import annotations

import asyncio
import unittest

from app.core.request_size_limit import (
    DEFAULT_BODY_LIMIT_BYTES,
    UPLOAD_BODY_LIMIT_BYTES,
    WEBHOOK_BODY_LIMIT_BYTES,
    RequestBodyLimitMiddleware,
    get_request_body_limit,
)


class RequestBodyLimitMiddlewareTests(unittest.TestCase):
    def test_sensitive_paths_use_expected_limits(self):
        self.assertEqual(get_request_body_limit("/api/stripe/webhook"), WEBHOOK_BODY_LIMIT_BYTES)
        self.assertEqual(get_request_body_limit("/api/paypal/webhook"), WEBHOOK_BODY_LIMIT_BYTES)
        self.assertEqual(get_request_body_limit("/api/upload/review"), DEFAULT_BODY_LIMIT_BYTES)
        self.assertEqual(get_request_body_limit("/api/reviews"), DEFAULT_BODY_LIMIT_BYTES)

    def test_chunked_body_is_rejected_before_application_buffers_it(self):
        app_started = False

        async def app(scope, receive, send):
            nonlocal app_started
            app_started = True
            while True:
                message = await receive()
                if not message.get("more_body"):
                    break
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = RequestBodyLimitMiddleware(app)
        messages = iter(
            [
                {
                    "type": "http.request",
                    "body": b"x" * DEFAULT_BODY_LIMIT_BYTES,
                    "more_body": True,
                },
                {"type": "http.request", "body": b"x", "more_body": False},
            ]
        )
        sent: list[dict] = []

        async def receive():
            return next(messages)

        async def send(message):
            sent.append(message)

        asyncio.run(
            middleware(
                {"type": "http", "path": "/api/reviews", "headers": []},
                receive,
                send,
            )
        )

        self.assertTrue(app_started)
        self.assertEqual(sent[0]["type"], "http.response.start")
        self.assertEqual(sent[0]["status"], 413)

    def test_content_length_is_rejected_without_entering_application(self):
        app_started = False

        async def app(scope, receive, send):
            nonlocal app_started
            app_started = True

        middleware = RequestBodyLimitMiddleware(app)
        sent: list[dict] = []

        async def receive():
            return {"type": "http.disconnect"}

        async def send(message):
            sent.append(message)

        asyncio.run(
            middleware(
                {
                    "type": "http",
                    "path": "/api/stripe/webhook",
                    "headers": [
                        (
                            b"content-length",
                            str(WEBHOOK_BODY_LIMIT_BYTES + 1).encode("ascii"),
                        )
                    ],
                },
                receive,
                send,
            )
        )

        self.assertFalse(app_started)
        self.assertEqual(sent[0]["status"], 413)


if __name__ == "__main__":
    unittest.main()
