from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import stripe

from app.models.enums import OrderStatus
from app.services.paypal import paypal_extract_order_metadata


_CODE_MAX_LENGTH = 120
_MESSAGE_MAX_LENGTH = 500
_DETAILS_MAX_LENGTH = 2000
_STAGE_MAX_LENGTH = 80


@dataclass(slots=True, frozen=True)
class PaymentFailureDiagnostics:
    stage: str
    code: str | None = None
    message: str | None = None
    details: str | None = None


def _clean_text(value: object, *, max_length: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:max_length]


def _read_attr(obj: object, key: str) -> object:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _format_details(*pairs: tuple[str, object]) -> str | None:
    details: list[str] = []
    for label, value in pairs:
        cleaned = _clean_text(value, max_length=400)
        if cleaned:
            details.append(f"{label}: {cleaned}")
    if not details:
        return None
    return _clean_text("; ".join(details), max_length=_DETAILS_MAX_LENGTH)


def _stringify_exception(exc: Exception | None) -> str | None:
    if exc is None:
        return None
    return _clean_text(str(exc), max_length=600)


def apply_order_values(order: object, values: dict[str, Any]) -> None:
    for key, value in values.items():
        setattr(order, key, value)


def payment_failure_values(
    diagnostics: PaymentFailureDiagnostics,
    **extra_values: Any,
) -> dict[str, Any]:
    values = {
        "status": OrderStatus.FAILED,
        "payment_failure_stage": _clean_text(
            diagnostics.stage, max_length=_STAGE_MAX_LENGTH
        ),
        "payment_failure_code": _clean_text(
            diagnostics.code, max_length=_CODE_MAX_LENGTH
        ),
        "payment_failure_message": _clean_text(
            diagnostics.message, max_length=_MESSAGE_MAX_LENGTH
        ),
        "payment_failure_details": _clean_text(
            diagnostics.details, max_length=_DETAILS_MAX_LENGTH
        ),
        "payment_failed_at": datetime.now(timezone.utc),
    }
    values.update(extra_values)
    return values


def payment_attempt_failure_values(
    diagnostics: PaymentFailureDiagnostics,
    **extra_values: Any,
) -> dict[str, Any]:
    """Persist the latest diagnostic without closing a retryable checkout."""
    values = {
        "payment_failure_stage": _clean_text(
            diagnostics.stage, max_length=_STAGE_MAX_LENGTH
        ),
        "payment_failure_code": _clean_text(
            diagnostics.code, max_length=_CODE_MAX_LENGTH
        ),
        "payment_failure_message": _clean_text(
            diagnostics.message, max_length=_MESSAGE_MAX_LENGTH
        ),
        "payment_failure_details": _clean_text(
            diagnostics.details, max_length=_DETAILS_MAX_LENGTH
        ),
        "payment_failed_at": datetime.now(timezone.utc),
    }
    values.update(extra_values)
    return values


def payment_success_values(**extra_values: Any) -> dict[str, Any]:
    values = {
        "status": OrderStatus.PAID,
        "payment_failure_stage": None,
        "payment_failure_code": None,
        "payment_failure_message": None,
        "payment_failure_details": None,
        "payment_failed_at": None,
    }
    values.update(extra_values)
    return values


def build_exception_failure_diagnostics(
    *,
    stage: str,
    code: str,
    message: str,
    exc: Exception | None = None,
    provider: str | None = None,
    extra_details: dict[str, object] | None = None,
) -> PaymentFailureDiagnostics:
    provider_code = _read_attr(exc, "code") if exc is not None else None
    request_id = _read_attr(exc, "request_id") if exc is not None else None
    http_status = _read_attr(exc, "http_status") if exc is not None else None
    if http_status is None and exc is not None:
        http_status = _read_attr(exc, "status_code")
    details_pairs: list[tuple[str, object]] = [
        ("Provider", provider),
        ("Exception type", type(exc).__name__ if exc is not None else None),
        ("Error code", provider_code),
        ("HTTP status", http_status),
        ("Request ID", request_id),
        ("Error", _stringify_exception(exc)),
    ]
    if extra_details:
        details_pairs.extend((key, value) for key, value in extra_details.items())
    return PaymentFailureDiagnostics(
        stage=stage,
        code=str(provider_code or code),
        message=message,
        details=_format_details(*details_pairs),
    )


def resolve_stripe_payment_intent(payment_intent: object) -> object | None:
    if not payment_intent:
        return None
    if isinstance(payment_intent, str):
        try:
            return stripe.PaymentIntent.retrieve(
                payment_intent, expand=["latest_charge"]
            )
        except Exception:
            return None
    return payment_intent


def build_stripe_payment_intent_failure_diagnostics(
    payment_intent: object,
    *,
    event_type: str | None = None,
) -> PaymentFailureDiagnostics:
    intent = resolve_stripe_payment_intent(payment_intent) or payment_intent
    last_error = _read_attr(intent, "last_payment_error")
    error_code = _read_attr(last_error, "code")
    decline_code = _read_attr(last_error, "decline_code")
    message = _read_attr(last_error, "message")
    intent_status = _read_attr(intent, "status")
    latest_charge = _read_attr(intent, "latest_charge")
    charge_outcome = _read_attr(latest_charge, "outcome")

    if not message:
        if event_type == "payment_intent.canceled" or str(intent_status or "").lower() == "canceled":
            message = "Stripe canceled the payment before it completed."
        else:
            message = "Stripe could not complete the payment."

    return PaymentFailureDiagnostics(
        stage="stripe_payment_intent",
        code=str(error_code or decline_code or intent_status or event_type or "stripe_payment_failed"),
        message=str(message),
        details=_format_details(
            ("Stripe event", event_type),
            ("PaymentIntent ID", _read_attr(intent, "id")),
            ("Intent status", intent_status),
            ("Error type", _read_attr(last_error, "type")),
            ("Error code", error_code),
            ("Decline code", decline_code),
            ("Provider message", message),
            ("Latest charge ID", _read_attr(latest_charge, "id")),
            ("Charge status", _read_attr(latest_charge, "status")),
            ("Charge failure code", _read_attr(latest_charge, "failure_code")),
            ("Charge failure message", _read_attr(latest_charge, "failure_message")),
            ("Outcome type", _read_attr(charge_outcome, "type")),
            ("Outcome reason", _read_attr(charge_outcome, "reason")),
            ("Network status", _read_attr(charge_outcome, "network_status")),
            ("Seller message", _read_attr(charge_outcome, "seller_message")),
        ),
    )


def build_stripe_session_failure_diagnostics(
    session: object,
    *,
    event_type: str | None = None,
) -> PaymentFailureDiagnostics:
    session_status = _read_attr(session, "status")
    payment_status = _read_attr(session, "payment_status")
    payment_intent = resolve_stripe_payment_intent(_read_attr(session, "payment_intent"))
    intent_diagnostics = (
        build_stripe_payment_intent_failure_diagnostics(
            payment_intent,
            event_type=event_type,
        )
        if payment_intent
        else None
    )
    message = intent_diagnostics.message if intent_diagnostics else None
    code = intent_diagnostics.code if intent_diagnostics else None

    normalized_event = (event_type or "").strip().lower()
    normalized_session_status = str(session_status or "").strip().lower()
    normalized_payment_status = str(payment_status or "").strip().lower()
    if normalized_event == "checkout.session.expired" or normalized_session_status == "expired":
        code = code or "session_expired"
        message = message or "Customer did not complete Stripe Checkout before the session expired."
    elif normalized_event == "checkout.session.async_payment_failed":
        code = code or "async_payment_failed"
        message = message or "Stripe reported that the asynchronous payment failed."
    elif normalized_session_status == "complete" and normalized_payment_status == "unpaid":
        code = code or "checkout_unpaid"
        message = message or "Stripe Checkout completed without a successful payment."
    else:
        code = code or "stripe_checkout_failed"
        message = message or "Stripe Checkout did not complete successfully."

    details = _format_details(
        ("Stripe event", event_type),
        ("Session ID", _read_attr(session, "id")),
        ("Session status", session_status),
        ("Payment status", payment_status),
        ("PaymentIntent ID", _read_attr(payment_intent, "id") if payment_intent else None),
        (
            "Intent status",
            _read_attr(payment_intent, "status") if payment_intent else None,
        ),
        ("Failure code", intent_diagnostics.code if intent_diagnostics else None),
        ("Failure details", intent_diagnostics.details if intent_diagnostics else None),
    )
    return PaymentFailureDiagnostics(
        stage="stripe_checkout",
        code=str(code),
        message=str(message),
        details=details,
    )


def _extract_paypal_capture(payload: dict[str, Any]) -> dict[str, Any] | None:
    units = payload.get("purchase_units")
    if not isinstance(units, list) or not units:
        return None
    first_unit = units[0]
    if not isinstance(first_unit, dict):
        return None
    payments = first_unit.get("payments")
    if not isinstance(payments, dict):
        return None
    captures = payments.get("captures")
    if not isinstance(captures, list) or not captures:
        return None
    first_capture = captures[0]
    if not isinstance(first_capture, dict):
        return None
    return first_capture


def build_paypal_failure_diagnostics(
    payload: dict[str, Any],
    *,
    event_type: str | None = None,
    fallback_message: str | None = None,
) -> PaymentFailureDiagnostics:
    metadata = paypal_extract_order_metadata(payload)
    order_status = metadata.get("status")
    capture_status = metadata.get("capture_status")
    capture_id = metadata.get("capture_id")
    capture = _extract_paypal_capture(payload)
    status_reason = None
    processor_response_code = None
    avs_code = None
    cvv_code = None
    if isinstance(capture, dict):
        status_details = capture.get("status_details")
        if isinstance(status_details, dict):
            status_reason = status_details.get("reason")
        processor_response = capture.get("processor_response")
        if isinstance(processor_response, dict):
            processor_response_code = processor_response.get("response_code")
            avs_code = processor_response.get("avs_code")
            cvv_code = processor_response.get("cvv_code")

    stage = "paypal_capture" if capture_status else "paypal_order"
    code = capture_status or order_status or event_type or "paypal_payment_failed"
    message = fallback_message
    if capture_status == "DECLINED":
        message = message or "PayPal capture was declined by the payer's funding source."
    elif capture_status == "DENIED":
        message = message or "PayPal denied the payment capture."
    elif capture_status == "FAILED":
        message = message or "PayPal capture failed before the payment completed."
    elif order_status in {"VOIDED", "CANCELED", "CANCELLED"}:
        message = message or "PayPal order was canceled or voided before capture."
    elif order_status in {"CREATED", "SAVED", "PAYER_ACTION_REQUIRED", "APPROVED"}:
        message = message or "PayPal checkout was not completed by the customer."
    else:
        message = message or "PayPal payment did not complete successfully."

    return PaymentFailureDiagnostics(
        stage=stage,
        code=str(code),
        message=str(message),
        details=_format_details(
            ("PayPal event", event_type),
            ("Order ID", payload.get("id")),
            ("Order status", order_status),
            ("Capture ID", capture_id),
            ("Capture status", capture_status),
            ("Reason", status_reason),
            ("Processor response", processor_response_code),
            ("AVS code", avs_code),
            ("CVV code", cvv_code),
        ),
    )


def build_timeout_failure_diagnostics(
    *,
    has_provider_session: bool,
) -> PaymentFailureDiagnostics:
    if has_provider_session:
        return PaymentFailureDiagnostics(
            stage="checkout_timeout",
            code="pending_timeout",
            message="Payment stayed pending too long and was closed automatically.",
            details="The checkout remained in PENDING beyond the allowed confirmation window.",
        )
    return PaymentFailureDiagnostics(
        stage="checkout_setup_timeout",
        code="checkout_setup_timeout",
        message="Checkout timed out before a payment session was fully created.",
        details="No Stripe session or PayPal order was linked before the pending checkout expired.",
    )
