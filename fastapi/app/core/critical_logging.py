from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from queue import Empty, Full, Queue
from threading import Event, Thread
from typing import Any

import httpx
from fastapi import Request

from app.core.config import settings
from app.core.rate_limit import client_rate_limit_key

CRITICAL_LOGGER_NAME = "app.critical"
DEFAULT_BETTERSTACK_INGEST_URL = "https://in.logs.betterstack.com"

_SENSITIVE_KEYS = {
    "address",
    "authorization",
    "code",
    "cookie",
    "delivery_address",
    "email",
    "id_token",
    "message",
    "name",
    "otp",
    "password",
    "phone",
    "refresh_token",
    "token",
    "x_api_key",
}


def _mask_email(value: str) -> str:
    if "@" not in value:
        return "***"
    local, domain = value.split("@", 1)
    if len(local) <= 2:
        return f"{local[:1]}***@{domain}"
    return f"{local[:2]}***@{domain}"


def _mask_phone(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) <= 4:
        return "***"
    return f"***{digits[-4:]}"


def _mask_sensitive(key: str, value: Any) -> Any:
    lowered = key.lower()
    if lowered not in _SENSITIVE_KEYS:
        return value
    if value is None:
        return None
    if "email" in lowered and isinstance(value, str):
        return _mask_email(value)
    if "phone" in lowered and isinstance(value, str):
        return _mask_phone(value)
    return "***"


def sanitize_context(value: Any, parent_key: str = "") -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, nested in value.items():
            masked = _mask_sensitive(str(key), nested)
            if masked != nested:
                sanitized[str(key)] = masked
                continue
            sanitized[str(key)] = sanitize_context(nested, str(key))
        return sanitized
    if isinstance(value, list):
        return [sanitize_context(item, parent_key) for item in value[:25]]
    if isinstance(value, tuple):
        return tuple(sanitize_context(item, parent_key) for item in value[:25])
    if isinstance(value, str):
        if parent_key.lower() in _SENSITIVE_KEYS:
            return _mask_sensitive(parent_key, value)
        return value[:500]
    return value


def _extract_request_context(request: Request | None) -> dict[str, Any] | None:
    if request is None:
        return None

    request_data = {
        "method": request.method,
        "path": request.url.path,
        "request_id": request.headers.get("x-request-id"),
        # Use exactly the same trusted-proxy policy as rate limiting.  Client
        # supplied X-Forwarded-For/X-Real-IP must never poison incident logs
        # when the application is deployed without a trusted proxy.
        "client_ip": client_rate_limit_key(request),
    }
    return sanitize_context(request_data)


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        created_at = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        payload: dict[str, Any] = {
            "dt": created_at,
            "timestamp": created_at,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        domain = getattr(record, "domain", None)
        if domain:
            payload["domain"] = domain
        event = getattr(record, "event", None)
        if event:
            payload["event"] = event
        context = getattr(record, "context", None)
        if context:
            payload["context"] = context
        request_data = getattr(record, "request_data", None)
        if request_data:
            payload["request"] = request_data

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


class _BetterStackHandler(logging.Handler):
    """Ship logs off the request path through a bounded worker queue.

    A synchronous network handler can pause an async request for its entire
    HTTP timeout.  The queue intentionally drops excess telemetry under a
    Better Stack outage instead of trading application availability for
    observability.  Critical events still go to the local stderr handler.
    """

    _STOP = object()

    def __init__(self, source_token: str, ingest_url: str) -> None:
        super().__init__()
        self._source_token = source_token
        self._ingest_url = ingest_url.rstrip("/")
        self._queue: Queue[bytes | object] = Queue(maxsize=1_000)
        self._closed = Event()
        self._worker = Thread(
            target=self._send_loop,
            name="betterstack-log-worker",
            daemon=True,
        )
        self._worker.start()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if self._closed.is_set():
                return
            rendered = self.format(record).encode("utf-8")
            self._queue.put_nowait(rendered)
        except Full:
            # The console handler remains synchronous and provides a durable
            # fallback for the process supervisor.  Do not recursively log a
            # telemetry drop from a logging handler.
            return
        except Exception:
            # Never fail request flow because of logging/serialization.
            return

    def _send_loop(self) -> None:
        timeout = httpx.Timeout(timeout=2.5, connect=1.0)
        with httpx.Client(timeout=timeout) as client:
            while True:
                payload = self._queue.get()
                try:
                    if payload is self._STOP:
                        return
                    client.post(
                        self._ingest_url,
                        content=payload,
                        headers={
                            "Authorization": f"Bearer {self._source_token}",
                            "Content-Type": "application/json",
                        },
                    )
                except Exception:
                    # Logging transport must not affect application traffic.
                    continue
                finally:
                    self._queue.task_done()

    def close(self) -> None:
        if not self._closed.is_set():
            self._closed.set()
            try:
                self._queue.put_nowait(self._STOP)
            except Full:
                # Make room for shutdown without waiting on a slow network
                # request.  The worker is daemonized as a final safeguard.
                try:
                    self._queue.get_nowait()
                    self._queue.task_done()
                except Empty:
                    pass
                try:
                    self._queue.put_nowait(self._STOP)
                except Full:
                    pass
            self._worker.join(timeout=2.0)
        super().close()


def _resolve_level(name: str) -> int:
    value = (name or "INFO").strip().upper()
    if value in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        return getattr(logging, value)
    return logging.INFO


def _resolve_ingest_url(raw: str | None) -> str:
    value = (raw or "").strip()
    if not value:
        return DEFAULT_BETTERSTACK_INGEST_URL
    if value.startswith("http://") or value.startswith("https://"):
        return value.rstrip("/")
    return f"https://{value.rstrip('/')}"


def setup_critical_logging() -> None:
    logger = logging.getLogger(CRITICAL_LOGGER_NAME)
    if getattr(logger, "_aib_critical_configured", False):
        return

    logger.setLevel(_resolve_level(settings.log_level))
    logger.propagate = False

    formatter = _JsonFormatter()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    source_token = (settings.betterstack_source_token or "").strip()
    if source_token:
        ingest_url = _resolve_ingest_url(settings.betterstack_ingest_url)
        betterstack_handler = _BetterStackHandler(source_token=source_token, ingest_url=ingest_url)
        betterstack_handler.setFormatter(formatter)
        logger.addHandler(betterstack_handler)

    logger._aib_critical_configured = True  # type: ignore[attr-defined]


def infer_domain_from_path(path: str) -> str:
    normalized = (path or "").lower()
    if normalized.startswith("/api/auth"):
        return "auth"
    if normalized.startswith("/api/users"):
        return "auth"
    if normalized.startswith("/api/promotions") or normalized.startswith("/api/settings") or normalized.startswith("/api/upload"):
        return "admin"
    if normalized.startswith("/api/orders"):
        return "payment"
    if normalized.startswith("/api/checkout") or normalized.startswith("/api/stripe") or normalized.startswith("/api/paypal"):
        return "payment"
    if normalized.startswith("/api/delivery"):
        return "cart"
    if normalized.startswith("/api/contact"):
        return "messaging"
    if normalized.startswith("/api/admin") or "/admin/" in normalized:
        return "admin"
    if normalized.startswith("/api/catalog") or normalized.startswith("/api/bouquets"):
        return "cart"
    return "system"


def log_critical_event(
    *,
    domain: str,
    event: str,
    message: str,
    request: Request | None = None,
    context: dict[str, Any] | None = None,
    exc: Exception | None = None,
    level: int = logging.ERROR,
) -> None:
    logger = logging.getLogger(CRITICAL_LOGGER_NAME)

    payload_context = sanitize_context(context or {})
    request_data = _extract_request_context(request)

    extra = {
        "domain": domain,
        "event": event,
        "context": payload_context,
        "request_data": request_data,
    }

    if exc is not None:
        logger.log(level, message, extra=extra, exc_info=(type(exc), exc, exc.__traceback__))
        return
    logger.log(level, message, extra=extra)
