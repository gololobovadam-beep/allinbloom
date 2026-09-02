from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Optional

import httpx

from app.core.config import settings


FREE_DELIVERY_MAX_MILES = 10
DELIVERY_MAX_MILES = 29.99
DELIVERY_BASE_FEE_CENTS = 2_000
DELIVERY_ADDITIONAL_MILE_FEE_CENTS = 200


@dataclass
class DeliveryQuote:
    ok: bool
    miles: Optional[float] = None
    distance_text: Optional[str] = None
    fee_cents: Optional[int] = None
    base_address: Optional[str] = None
    formatted_address: Optional[str] = None
    error: Optional[str] = None
    stage: Optional[str] = None
    code: Optional[str] = None
    provider: Optional[str] = None
    provider_status: Optional[str] = None
    provider_http_status: Optional[int] = None
    details: dict[str, Any] | None = None


@dataclass
class DeliveryValidationResult:
    ok: bool
    formatted_address: Optional[str] = None
    error: Optional[str] = None
    code: Optional[str] = None
    provider_status: Optional[str] = None
    provider_http_status: Optional[int] = None
    details: dict[str, Any] | None = None


def summarize_delivery_address_input(raw_address: str) -> dict[str, Any]:
    trimmed = raw_address.strip()
    segments = [segment.strip() for segment in trimmed.split(",") if segment.strip()]
    return {
        "address_length": len(trimmed),
        "address_segment_count": len(segments),
        "address_has_digit": any(char.isdigit() for char in trimmed),
        "address_has_comma": "," in trimmed,
    }


def build_delivery_quote_log_context(raw_address: str, quote: DeliveryQuote) -> dict[str, Any]:
    context = summarize_delivery_address_input(raw_address)
    context["delivery_stage"] = quote.stage or "unknown"
    context["delivery_code"] = quote.code or "delivery_quote_failed"
    if quote.provider:
        context["delivery_provider"] = quote.provider
    if quote.provider_status:
        context["delivery_provider_status"] = quote.provider_status
    if quote.provider_http_status is not None:
        context["delivery_provider_http_status"] = quote.provider_http_status
    if quote.miles is not None:
        context["delivery_miles"] = quote.miles
    if quote.fee_cents is not None:
        context["delivery_fee_cents"] = quote.fee_cents
    if quote.error:
        context["delivery_error"] = quote.error
    if quote.details:
        context["delivery_details"] = quote.details
    return context


def delivery_quote_failure_level(quote: DeliveryQuote) -> int:
    technical_failure_codes = {
        "delivery_not_configured",
        "geocode_request_failed",
        "geocode_http_error",
        "geocode_invalid_payload",
        "geocode_status_invalid",
        "distance_matrix_request_failed",
        "distance_matrix_http_error",
        "distance_matrix_invalid_payload",
        "distance_matrix_status_invalid",
        "distance_matrix_distance_missing",
    }
    if (quote.code or "") in technical_failure_codes:
        return logging.ERROR
    return logging.WARNING


def _build_failed_quote(
    *,
    error: str,
    stage: str,
    code: str,
    provider: str | None = None,
    provider_status: str | None = None,
    provider_http_status: int | None = None,
    details: dict[str, Any] | None = None,
) -> DeliveryQuote:
    return DeliveryQuote(
        ok=False,
        error=error,
        stage=stage,
        code=code,
        provider=provider,
        provider_status=provider_status,
        provider_http_status=provider_http_status,
        details=details,
    )


def _validate_address_format_details(address: str) -> tuple[Optional[str], Optional[str]]:
    trimmed = address.strip()
    if len(trimmed) < 10:
        return "Address is too short. Please provide a complete address.", "address_too_short"
    if not any(char.isdigit() for char in trimmed):
        return "Please include a street number.", "address_missing_street_number"
    if "," not in trimmed:
        return (
            "Please provide a complete address with city and state (e.g., 123 Main St, Chicago, IL).",
            "address_missing_city_state",
        )
    return None, None


def _validate_address_format(address: str) -> Optional[str]:
    error, _code = _validate_address_format_details(address)
    return error


async def _validate_and_geocode(address: str, api_key: str) -> DeliveryValidationResult:
    params = {"address": address, "key": api_key}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                "https://maps.googleapis.com/maps/api/geocode/json", params=params
            )
    except httpx.HTTPError:
        return DeliveryValidationResult(
            ok=False,
            error="Unable to validate address.",
            code="geocode_request_failed",
        )
    if response.status_code != 200:
        return DeliveryValidationResult(
            ok=False,
            error="Unable to validate address.",
            code="geocode_http_error",
            provider_http_status=response.status_code,
        )
    try:
        data = response.json()
    except ValueError:
        return DeliveryValidationResult(
            ok=False,
            error="Unable to validate address.",
            code="geocode_invalid_payload",
        )
    status = data.get("status")
    results = data.get("results") or []
    if status == "ZERO_RESULTS":
        return DeliveryValidationResult(
            ok=False,
            error="Address not found. Please check and try again.",
            code="address_not_found",
            provider_status="ZERO_RESULTS",
        )
    if status != "OK" or not results:
        return DeliveryValidationResult(
            ok=False,
            error="Unable to validate address.",
            code="geocode_status_invalid",
            provider_status=str(status or "unknown"),
            details={"results_count": len(results)},
        )

    result = results[0]
    types = result.get("types") or []
    is_vague = any(
        t in ["country", "administrative_area_level_1", "administrative_area_level_2", "locality"]
        for t in types
    ) and "street_address" not in types and "premise" not in types
    if is_vague:
        return DeliveryValidationResult(
            ok=False,
            error="Please provide a complete street address, not just a city.",
            code="address_too_vague",
            provider_status=str(status or "OK"),
            details={"result_types": types[:10]},
        )

    components = result.get("address_components") or []
    has_street_number = any("street_number" in (c.get("types") or []) for c in components)
    if not has_street_number:
        return DeliveryValidationResult(
            ok=False,
            error="Please include a street number in your address.",
            code="address_missing_street_number",
            provider_status=str(status or "OK"),
        )
    has_route = any("route" in (c.get("types") or []) for c in components)
    if not has_route:
        return DeliveryValidationResult(
            ok=False,
            error="Please include a street name in your address.",
            code="address_missing_street_name",
            provider_status=str(status or "OK"),
        )

    return DeliveryValidationResult(
        ok=True,
        formatted_address=result.get("formatted_address"),
        provider_status=str(status or "OK"),
    )


def get_delivery_fee_cents(miles: float) -> Optional[int]:
    if miles <= FREE_DELIVERY_MAX_MILES:
        return 0
    if miles > DELIVERY_MAX_MILES:
        return None

    # Charge the initial $20 for the first mile after the free radius, then
    # add $2 for every whole additional mile begun.  For example: 10.5 = $20,
    # 11.7 = $22, 12.4 = $24.
    completed_miles_after_free_radius = int(miles - FREE_DELIVERY_MAX_MILES)
    return DELIVERY_BASE_FEE_CENTS + (
        completed_miles_after_free_radius * DELIVERY_ADDITIONAL_MILE_FEE_CENTS
    )


async def get_delivery_quote(raw_address: str) -> DeliveryQuote:
    address = raw_address.strip()
    if not address:
        return _build_failed_quote(
            error="Delivery address is required.",
            stage="input_validation",
            code="delivery_address_missing",
        )

    api_key = settings.google_maps_api_key
    if not api_key:
        return _build_failed_quote(
            error="Delivery is not configured.",
            stage="configuration",
            code="delivery_not_configured",
            provider="google_maps",
        )

    format_error, format_code = _validate_address_format_details(address)
    if format_error:
        return _build_failed_quote(
            error=format_error,
            stage="input_validation",
            code=format_code or "delivery_address_invalid",
        )

    validation = await _validate_and_geocode(address, api_key)
    if not validation.ok or not validation.formatted_address:
        return _build_failed_quote(
            error=validation.error or "Unable to validate address.",
            stage="geocode_validation",
            code=validation.code or "delivery_address_invalid",
            provider="google_maps",
            provider_status=validation.provider_status,
            provider_http_status=validation.provider_http_status,
            details=validation.details,
        )

    formatted_address = validation.formatted_address

    base_address = settings.delivery_base_address
    params = {
        "origins": base_address,
        "destinations": formatted_address,
        "units": "imperial",
        "key": api_key,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                "https://maps.googleapis.com/maps/api/distancematrix/json", params=params
            )
    except httpx.HTTPError:
        return _build_failed_quote(
            error="Unable to calculate delivery distance.",
            stage="distance_matrix_request",
            code="distance_matrix_request_failed",
            provider="google_maps",
        )

    if response.status_code != 200:
        return _build_failed_quote(
            error="Unable to calculate delivery distance.",
            stage="distance_matrix_request",
            code="distance_matrix_http_error",
            provider="google_maps",
            provider_http_status=response.status_code,
        )
    try:
        data = response.json()
    except ValueError:
        return _build_failed_quote(
            error="Unable to calculate delivery distance.",
            stage="distance_matrix_request",
            code="distance_matrix_invalid_payload",
            provider="google_maps",
        )
    matrix_status = data.get("status")
    if matrix_status != "OK":
        return _build_failed_quote(
            error="Unable to calculate delivery distance.",
            stage="distance_matrix_response",
            code="distance_matrix_status_invalid",
            provider="google_maps",
            provider_status=str(matrix_status or "unknown"),
        )

    element = (data.get("rows") or [{}])[0].get("elements", [{}])[0]
    element_status = element.get("status")
    if element_status != "OK":
        return _build_failed_quote(
            error="Address not reachable for delivery.",
            stage="distance_matrix_response",
            code="distance_matrix_element_invalid",
            provider="google_maps",
            provider_status=str(matrix_status or "OK"),
            details={"element_status": str(element_status or "unknown")},
        )

    meters = (element.get("distance") or {}).get("value")
    if not isinstance(meters, (int, float)):
        return _build_failed_quote(
            error="Unable to calculate delivery distance.",
            stage="distance_matrix_response",
            code="distance_matrix_distance_missing",
            provider="google_maps",
            provider_status=str(matrix_status or "OK"),
        )

    miles = round((meters / 1609.344) * 100) / 100
    fee_cents = get_delivery_fee_cents(miles)
    if fee_cents is None:
        max_miles = DELIVERY_MAX_MILES
        return _build_failed_quote(
            error=(
                f"Delivery is available within {max_miles} miles of our studio. "
                f"Your address is {miles:.1f} miles away."
            ),
            stage="delivery_radius",
            code="delivery_out_of_range",
            provider="google_maps",
            details={"max_miles": max_miles, "calculated_miles": miles},
        )

    distance_text = (element.get("distance") or {}).get("text") or f"{miles:.1f} mi"

    return DeliveryQuote(
        ok=True,
        miles=miles,
        distance_text=distance_text,
        fee_cents=fee_cents,
        base_address=base_address,
        formatted_address=formatted_address,
        stage="complete",
        code="delivery_quote_ok",
        provider="google_maps",
        provider_status=str(matrix_status or "OK"),
    )
