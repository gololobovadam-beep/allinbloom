from __future__ import annotations

"""Small process-local guard for expensive public endpoints.

This is deliberately a backstop, not a replacement for an edge/WAF or a
shared Redis limiter.  It keeps one client from repeatedly spending Maps or
payment-provider quota in a single worker and is safe to use in tests and
local development.
"""

from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request, status

from app.core.config import settings


class SlidingWindowRateLimiter:
    def __init__(self, *, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True


def client_rate_limit_key(request: Request) -> str:
    """Only honor forwarding headers when the deployment explicitly trusts them."""
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            candidate = forwarded.split(",", 1)[0].strip()
            if candidate:
                return candidate
        candidate = (request.headers.get("x-real-ip") or "").strip()
        if candidate:
            return candidate
    return request.client.host if request.client and request.client.host else "unknown"


def enforce_rate_limit(
    request: Request,
    limiter: SlidingWindowRateLimiter,
    *,
    detail: str = "Too many requests. Please try again later.",
) -> None:
    if not limiter.allow(client_rate_limit_key(request)):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)
