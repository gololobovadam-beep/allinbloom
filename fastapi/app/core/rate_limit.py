from __future__ import annotations

"""Small process-local guard for expensive public endpoints.

This is deliberately a backstop, not a replacement for an edge/WAF or a
shared Redis limiter.  It keeps one client from repeatedly spending Maps or
payment-provider quota in a single worker and is safe to use in tests and
local development.
"""

from collections import deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request, status

from app.core.config import settings


class SlidingWindowRateLimiter:
    """A bounded, process-local sliding-window limiter.

    This class deliberately remains a local backstop.  A public production
    deployment must enforce the authoritative limit at a shared edge/Redis
    layer, because no in-process data structure can coordinate multiple
    workers.  The bounded cache is still useful when that external control is
    unavailable and, importantly, cannot grow without limit from spoofed
    client keys.
    """

    def __init__(
        self,
        *,
        limit: int,
        window_seconds: int,
        max_keys: int = 10_000,
        prune_interval: int = 128,
    ) -> None:
        if limit < 1:
            raise ValueError("limit must be positive")
        if window_seconds < 1:
            raise ValueError("window_seconds must be positive")
        if max_keys < 1:
            raise ValueError("max_keys must be positive")
        if prune_interval < 1:
            raise ValueError("prune_interval must be positive")

        self.limit = limit
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._prune_interval = prune_interval
        self._hits: dict[str, deque[float]] = {}
        self._calls_since_prune = 0
        self._lock = Lock()

    def _prune_expired(self, now: float) -> None:
        """Discard inactive client keys while holding ``self._lock``."""
        cutoff = now - self.window_seconds
        expired_keys: list[str] = []
        for key, hits in self._hits.items():
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if not hits:
                expired_keys.append(key)
        for key in expired_keys:
            del self._hits[key]

    def allow(self, key: str) -> bool:
        now = monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            self._calls_since_prune += 1
            if self._calls_since_prune >= self._prune_interval:
                self._prune_expired(now)
                self._calls_since_prune = 0

            hits = self._hits.get(key)
            if hits is None:
                # Prune once more before failing closed.  Refusing a new key
                # is preferable to an attacker allocating unbounded memory.
                if len(self._hits) >= self.max_keys:
                    self._prune_expired(now)
                if len(self._hits) >= self.max_keys:
                    return False
                hits = deque()
                self._hits[key] = hits

            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True


def client_rate_limit_key(request: Request) -> str:
    """Only honor forwarding headers when the deployment explicitly trusts them."""
    candidate = ""
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            candidate = forwarded.split(",", 1)[0].strip()
            if candidate:
                return candidate[:128]
        candidate = (request.headers.get("x-real-ip") or "").strip()
        if candidate:
            return candidate[:128]
    candidate = request.client.host if request.client and request.client.host else "unknown"
    return candidate[:128] or "unknown"


def enforce_rate_limit(
    request: Request,
    limiter: SlidingWindowRateLimiter,
    *,
    detail: str = "Too many requests. Please try again later.",
) -> None:
    if not limiter.allow(client_rate_limit_key(request)):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)
