from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from fastapi import Request

from app.core.config import settings
from app.core.critical_logging import _extract_request_context
from app.core.rate_limit import SlidingWindowRateLimiter, client_rate_limit_key


def _request(*, client_ip: str, forwarded_for: str | None = None) -> Request:
    headers = []
    if forwarded_for:
        headers.append((b"x-forwarded-for", forwarded_for.encode("ascii")))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/checkout",
            "headers": headers,
            "client": (client_ip, 1234),
            "scheme": "https",
            "server": ("api.example.test", 443),
        }
    )


class RateLimitReliabilityTests(unittest.TestCase):
    def test_limiter_fails_closed_at_bounded_key_capacity_and_prunes_expired_keys(self):
        limiter = SlidingWindowRateLimiter(
            limit=1,
            window_seconds=10,
            max_keys=2,
            prune_interval=1,
        )

        with patch("app.core.rate_limit.monotonic", return_value=0):
            self.assertTrue(limiter.allow("client-a"))
            self.assertTrue(limiter.allow("client-b"))
            self.assertFalse(limiter.allow("client-c"))

        with patch("app.core.rate_limit.monotonic", return_value=11):
            self.assertTrue(limiter.allow("client-c"))

    def test_untrusted_forwarding_headers_are_ignored_for_limits_and_critical_logs(self):
        request = _request(client_ip="203.0.113.10", forwarded_for="198.51.100.42")
        with patch.object(settings, "trust_proxy_headers", False):
            self.assertEqual(client_rate_limit_key(request), "203.0.113.10")
            self.assertEqual(_extract_request_context(request)["client_ip"], "203.0.113.10")

    def test_trusted_proxy_uses_the_first_forwarded_address(self):
        request = _request(
            client_ip="203.0.113.10",
            forwarded_for="198.51.100.42, 203.0.113.20",
        )
        with patch.object(settings, "trust_proxy_headers", True):
            self.assertEqual(client_rate_limit_key(request), "198.51.100.42")


if __name__ == "__main__":
    unittest.main()
