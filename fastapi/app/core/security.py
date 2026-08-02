from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hmac import compare_digest
from hashlib import sha256
import re
from secrets import randbelow, token_hex, token_urlsafe
from typing import Any

from jose import jwt

from app.core.config import settings


ALGORITHM = "HS256"
OTP_TTL_MINUTES = 10
# Checkout access is held in an HttpOnly, order-bound cookie so a browser
# history entry, referrer, analytics script, or payment provider never sees a
# bearer credential.
CHECKOUT_ACCESS_TOKEN_TTL_HOURS = 2
GOOGLE_OAUTH_STATE_TTL_MINUTES = 10
_SAFE_ORDER_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def _encode_token(subject: dict[str, Any], expires_delta: timedelta, token_type: str) -> str:
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {"exp": expire, "type": token_type, **subject}
    secret = settings.resolved_auth_secret()
    if not secret:
        raise RuntimeError("AUTH_SECRET is not configured")
    return jwt.encode(to_encode, secret, algorithm=ALGORITHM)


def _decode_token(token: str, token_type: str) -> dict[str, Any]:
    secret = settings.resolved_auth_secret()
    if not secret:
        raise RuntimeError("AUTH_SECRET is not configured")
    payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
    payload_type = payload.get("type")
    if token_type == "access" and payload_type is None:
        return payload
    if payload_type != token_type:
        raise ValueError("Invalid token type")
    return payload


def create_access_token(subject: dict[str, Any], expires_minutes: int | None = None) -> str:
    expire_minutes = expires_minutes or settings.access_token_expire_minutes
    return _encode_token(subject, timedelta(minutes=expire_minutes), "access")


def decode_access_token(token: str) -> dict[str, Any]:
    return _decode_token(token, "access")


def create_refresh_token(subject: dict[str, Any], expires_days: int | None = None) -> str:
    expire_days = expires_days or settings.refresh_token_expire_days
    return _encode_token(subject, timedelta(days=expire_days), "refresh")


def decode_refresh_token(token: str) -> dict[str, Any]:
    return _decode_token(token, "refresh")


def checkout_access_cookie_name(order_id: str) -> str:
    """Return a safe, per-order cookie name without reflecting user input."""
    normalized_order_id = (order_id or "").strip()
    if not _SAFE_ORDER_ID.fullmatch(normalized_order_id):
        raise ValueError("Invalid order id")
    return f"aib_checkout_{normalized_order_id}"


def create_checkout_access_token(
    *, order_id: str, expires_hours: int | None = None
) -> str:
    normalized_order_id = (order_id or "").strip()
    checkout_access_cookie_name(normalized_order_id)
    ttl_hours = expires_hours or CHECKOUT_ACCESS_TOKEN_TTL_HOURS
    return _encode_token(
        {"order_id": normalized_order_id},
        timedelta(hours=ttl_hours),
        "checkout_access",
    )


def decode_checkout_access_token(token: str) -> dict[str, Any]:
    payload = _decode_token(token, "checkout_access")
    order_id = payload.get("order_id")
    if not isinstance(order_id, str):
        raise ValueError("Invalid checkout access token")
    normalized_order_id = order_id.strip()
    checkout_access_cookie_name(normalized_order_id)
    return {"order_id": normalized_order_id}


def create_google_oauth_state_token(
    *, expires_minutes: int | None = None
) -> str:
    """Create a short-lived, signed OAuth state value for one browser flow."""
    ttl_minutes = expires_minutes or GOOGLE_OAUTH_STATE_TTL_MINUTES
    return _encode_token(
        {"nonce": token_urlsafe(32)},
        timedelta(minutes=ttl_minutes),
        "google_oauth_state",
    )


def validate_google_oauth_state_token(
    *, received_state: str | None, expected_state: str | None
) -> bool:
    """Require a matching HttpOnly cookie value and a valid signed state token."""
    received = (received_state or "").strip()
    expected = (expected_state or "").strip()
    if not received or not expected or not compare_digest(received, expected):
        return False
    try:
        payload = _decode_token(received, "google_oauth_state")
    except Exception:
        return False
    nonce = payload.get("nonce")
    return isinstance(nonce, str) and len(nonce) >= 32


def generate_otp() -> dict[str, str | datetime]:
    code = str(randbelow(900000) + 100000)
    salt = token_hex(16)
    code_hash = sha256(f"{code}{salt}".encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES)
    return {
        "code": code,
        "salt": salt,
        "hash": code_hash,
        "expires_at": expires_at,
    }


def verify_otp(code: str, salt: str, code_hash: str) -> bool:
    candidate = sha256(f"{code}{salt}".encode()).hexdigest()
    return compare_digest(candidate, code_hash)
