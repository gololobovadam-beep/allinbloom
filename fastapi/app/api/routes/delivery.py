from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.core.critical_logging import log_critical_event
from app.core.rate_limit import SlidingWindowRateLimiter, enforce_rate_limit
from app.schemas.delivery import DeliveryQuoteOut, DeliveryQuoteRequest
from app.services.delivery import (
    build_delivery_quote_log_context,
    delivery_quote_failure_level,
    get_delivery_quote,
)

router = APIRouter(prefix="/api/delivery", tags=["delivery"])
delivery_quote_limiter = SlidingWindowRateLimiter(limit=20, window_seconds=15 * 60)


@router.post("/quote", response_model=DeliveryQuoteOut)
async def quote_delivery(payload: DeliveryQuoteRequest, request: Request):
    enforce_rate_limit(request, delivery_quote_limiter)
    result = await get_delivery_quote(payload.address)
    if not result.ok:
        log_critical_event(
            domain="cart",
            event="delivery_quote_failed",
            message="Delivery quote request failed from cart.",
            request=request,
            context=build_delivery_quote_log_context(payload.address, result),
            level=delivery_quote_failure_level(result),
        )
        raise HTTPException(status_code=400, detail=result.error or "Unable to calculate delivery.")
    return DeliveryQuoteOut(
        fee_cents=result.fee_cents or 0,
        miles=result.miles or 0,
        distance_text=result.distance_text or "",
    )
