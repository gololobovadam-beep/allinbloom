from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
import time
from typing import Any, Mapping

import httpx

from app.core.config import settings


PAYPAL_TOKEN_LEEWAY_SECONDS = 60


@dataclass(slots=True)
class PayPalOrderResponse:
    order_id: str
    approve_url: str


class PayPalApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


_token_cache: dict[str, Any] = {"access_token": None, "expires_at": 0.0}


def paypal_is_configured() -> bool:
    return bool((settings.paypal_client_id or "").strip() and (settings.paypal_client_secret or "").strip())


def paypal_webhook_is_configured() -> bool:
    return bool(paypal_is_configured() and (settings.paypal_webhook_id or "").strip())


def _paypal_base_url() -> str:
    env = (settings.paypal_env or "sandbox").strip().lower()
    if env == "live":
        return "https://api-m.paypal.com"
    return "https://api-m.sandbox.paypal.com"


def _format_amount(cents: int) -> str:
    value = (Decimal(cents) / Decimal(100)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return f"{value:.2f}"


def _operation_request_id(operation: str, stable_id: str) -> str:
    """Return a provider-safe deterministic idempotency key (max 108 chars)."""
    digest = sha256(f"{operation}:{stable_id}".encode("utf-8")).hexdigest()
    return f"aib-{operation}-{digest[:48]}"


def _parse_amount_cents(value: object) -> int | None:
    if value is None:
        return None
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None
    return int(amount * 100)


def _extract_purchase_unit(order: dict[str, Any]) -> dict[str, Any] | None:
    units = order.get("purchase_units")
    if isinstance(units, list) and units:
        first = units[0]
        if isinstance(first, dict):
            return first
    return None


def _extract_approval_url(order: dict[str, Any]) -> str | None:
    links = order.get("links")
    if not isinstance(links, list):
        return None
    for link in links:
        if not isinstance(link, dict):
            continue
        rel = (link.get("rel") or "").lower()
        if rel in {"approve", "payer-action"}:
            href = link.get("href")
            if isinstance(href, str) and href.strip():
                return href
    return None


def _extract_capture_id(order: dict[str, Any]) -> str | None:
    unit = _extract_purchase_unit(order)
    if not unit:
        return None
    payments = unit.get("payments")
    if not isinstance(payments, dict):
        return None
    captures = payments.get("captures")
    if not isinstance(captures, list) or not captures:
        return None
    capture = captures[0]
    if not isinstance(capture, dict):
        return None
    capture_id = capture.get("id")
    if isinstance(capture_id, str) and capture_id.strip():
        return capture_id
    return None


def _extract_capture_status(order: dict[str, Any]) -> str | None:
    unit = _extract_purchase_unit(order)
    if not unit:
        return None
    payments = unit.get("payments")
    if not isinstance(payments, dict):
        return None
    captures = payments.get("captures")
    if not isinstance(captures, list) or not captures:
        return None
    capture = captures[0]
    if not isinstance(capture, dict):
        return None
    status = capture.get("status")
    if isinstance(status, str) and status.strip():
        return status.strip().upper()
    return None


def _extract_custom_id(order: dict[str, Any]) -> str | None:
    unit = _extract_purchase_unit(order)
    if not unit:
        return None
    custom_id = unit.get("custom_id") or unit.get("invoice_id")
    if isinstance(custom_id, str) and custom_id.strip():
        return custom_id
    return None


def _extract_amount(order: dict[str, Any]) -> tuple[int | None, str | None]:
    unit = _extract_purchase_unit(order)
    if not unit:
        return None, None
    amount = unit.get("amount")
    if not isinstance(amount, dict):
        return None, None
    value = _parse_amount_cents(amount.get("value"))
    currency = amount.get("currency_code")
    if isinstance(currency, str) and currency.strip():
        currency_value = currency.strip().upper()
    else:
        currency_value = None
    return value, currency_value


def _get_access_token() -> str:
    if not paypal_is_configured():
        raise PayPalApiError("PayPal is not configured.")

    now = time.time()
    cached = _token_cache.get("access_token")
    expires_at = float(_token_cache.get("expires_at") or 0)
    if isinstance(cached, str) and cached and expires_at - PAYPAL_TOKEN_LEEWAY_SECONDS > now:
        return cached

    base_url = _paypal_base_url()
    client_id = settings.paypal_client_id or ""
    client_secret = settings.paypal_client_secret or ""

    with httpx.Client(timeout=8) as client:
        response = client.post(
            f"{base_url}/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
            headers={"Accept": "application/json", "Accept-Language": "en_US"},
        )

    if response.status_code >= 400:
        raise PayPalApiError(
            f"PayPal token request failed: HTTP {response.status_code}",
            status_code=response.status_code,
        )

    payload = response.json()
    token = payload.get("access_token")
    expires_in = payload.get("expires_in") or 0
    if not isinstance(token, str) or not token.strip():
        raise PayPalApiError("PayPal token response missing access_token.")

    _token_cache["access_token"] = token
    _token_cache["expires_at"] = now + int(expires_in or 0)
    return token


def _paypal_request(
    method: str,
    path: str,
    *,
    json: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    token = _get_access_token()
    base_url = _paypal_base_url()
    req_headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)

    with httpx.Client(timeout=10) as client:
        response = client.request(
            method,
            f"{base_url}{path}",
            json=json,
            headers=req_headers,
        )

    if response.status_code >= 400:
        raise PayPalApiError(
            f"PayPal API error: HTTP {response.status_code}",
            status_code=response.status_code,
        )

    if response.status_code == 204 or not response.content:
        return {}

    payload = response.json()
    if not isinstance(payload, dict):
        raise PayPalApiError("PayPal API response is not JSON object.")
    return payload


def _build_payer_payload(
    *,
    email: str | None,
    full_name: str | None,
) -> dict[str, Any] | None:
    payer: dict[str, Any] = {}

    clean_email = (email or "").strip().lower()
    if clean_email and "@" in clean_email:
        payer["email_address"] = clean_email

    clean_name = (full_name or "").strip()
    if clean_name:
        name_parts = [part for part in clean_name.split() if part]
        if name_parts:
            payer_name: dict[str, str] = {"given_name": name_parts[0]}
            if len(name_parts) > 1:
                payer_name["surname"] = " ".join(name_parts[1:])
            payer["name"] = payer_name

    return payer or None


def paypal_create_order(
    *,
    order_id: str,
    total_cents: int,
    currency: str,
    payer_email: str | None = None,
    payer_name: str | None = None,
    return_url: str,
    cancel_url: str,
) -> PayPalOrderResponse:
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": order_id,
                "custom_id": order_id,
                "invoice_id": order_id,
                "amount": {
                    "currency_code": currency.upper(),
                    "value": _format_amount(total_cents),
                },
            }
        ],
        "application_context": {
            "return_url": return_url,
            "cancel_url": cancel_url,
            "brand_name": "All in Bloom Floral Studio",
            "landing_page": "LOGIN",
            "user_action": "PAY_NOW",
            "shipping_preference": "NO_SHIPPING",
        },
    }
    payer = _build_payer_payload(email=payer_email, full_name=payer_name)
    if payer:
        payload["payer"] = payer

    response = _paypal_request(
        "POST",
        "/v2/checkout/orders",
        json=payload,
        headers={"PayPal-Request-Id": _operation_request_id("create", order_id)},
    )

    paypal_order_id = response.get("id")
    approve_url = _extract_approval_url(response)
    if not isinstance(paypal_order_id, str) or not paypal_order_id.strip():
        raise PayPalApiError("PayPal create order response missing id.")
    if not approve_url:
        raise PayPalApiError("PayPal create order response missing approval link.")

    return PayPalOrderResponse(order_id=paypal_order_id, approve_url=approve_url)


def paypal_get_order(paypal_order_id: str) -> dict[str, Any]:
    return _paypal_request("GET", f"/v2/checkout/orders/{paypal_order_id}")


def paypal_capture_order(
    paypal_order_id: str, *, request_id: str | None = None
) -> dict[str, Any]:
    stable_id = request_id or paypal_order_id
    return _paypal_request(
        "POST",
        f"/v2/checkout/orders/{paypal_order_id}/capture",
        headers={"PayPal-Request-Id": _operation_request_id("capture", stable_id)},
    )


def paypal_void_order(
    paypal_order_id: str, *, request_id: str | None = None
) -> dict[str, Any]:
    stable_id = request_id or paypal_order_id
    return _paypal_request(
        "POST",
        f"/v2/checkout/orders/{paypal_order_id}/void",
        headers={"PayPal-Request-Id": _operation_request_id("void", stable_id)},
    )


def paypal_extract_order_metadata(order: dict[str, Any]) -> dict[str, Any]:
    amount_cents, currency = _extract_amount(order)
    return {
        "custom_id": _extract_custom_id(order),
        "amount_cents": amount_cents,
        "currency": currency,
        "status": (order.get("status") or "").upper() if isinstance(order.get("status"), str) else None,
        "capture_id": _extract_capture_id(order),
        "capture_status": _extract_capture_status(order),
    }


def paypal_verify_webhook_signature(
    *,
    event_payload: dict[str, Any],
    headers: Mapping[str, str],
) -> bool:
    if not paypal_webhook_is_configured():
        raise PayPalApiError("PayPal webhook is not configured.")

    transmission_id = (headers.get("paypal-transmission-id") or "").strip()
    transmission_time = (headers.get("paypal-transmission-time") or "").strip()
    transmission_sig = (headers.get("paypal-transmission-sig") or "").strip()
    cert_url = (headers.get("paypal-cert-url") or "").strip()
    auth_algo = (headers.get("paypal-auth-algo") or "").strip()
    webhook_id = (settings.paypal_webhook_id or "").strip()

    if not all(
        [
            transmission_id,
            transmission_time,
            transmission_sig,
            cert_url,
            auth_algo,
            webhook_id,
        ]
    ):
        raise PayPalApiError("PayPal webhook headers are incomplete.")

    verification_payload = {
        "transmission_id": transmission_id,
        "transmission_time": transmission_time,
        "cert_url": cert_url,
        "auth_algo": auth_algo,
        "transmission_sig": transmission_sig,
        "webhook_id": webhook_id,
        "webhook_event": event_payload,
    }
    response = _paypal_request(
        "POST",
        "/v1/notifications/verify-webhook-signature",
        json=verification_payload,
    )
    status = response.get("verification_status")
    return isinstance(status, str) and status.upper() == "SUCCESS"
