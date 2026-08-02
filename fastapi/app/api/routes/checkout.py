from __future__ import annotations

import calendar
from datetime import date, datetime, timezone
import json
import logging
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, HTTPException, Request, Response
import stripe
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import _reject_cross_site_cookie_request, get_db, get_optional_user
from app.core.config import settings
from app.core.critical_logging import log_critical_event
from app.core.rate_limit import SlidingWindowRateLimiter, enforce_rate_limit
from app.core.security import (
    CHECKOUT_ACCESS_TOKEN_TTL_HOURS,
    checkout_access_cookie_name,
    create_checkout_access_token,
    decode_checkout_access_token,
)
from app.models.bouquet import Bouquet
from app.models.enums import BouquetType, CatalogType, OrderStatus
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.user import User
from app.schemas.checkout import (
    CheckoutCancelRequest,
    CheckoutCancelResponse,
    CheckoutEventRequest,
    CheckoutEventResponse,
    CheckoutRequest,
    CheckoutResponse,
    CheckoutStatusRequest,
    CheckoutStatusResponse,
)
from app.services.delivery import (
    build_delivery_quote_log_context,
    delivery_quote_failure_level,
    get_delivery_quote,
)
from app.services.orders import (
    STRIPE_CHECKOUT_SESSION_EXPIRATION_SECONDS,
    expire_pending_orders,
    resolve_order_status_from_paypal_order,
    resolve_order_status_from_session,
    sync_order_with_paypal,
    sync_order_with_stripe,
)
from app.services.payment_diagnostics import (
    build_exception_failure_diagnostics,
    build_paypal_failure_diagnostics,
    build_stripe_session_failure_diagnostics,
    payment_failure_values,
    payment_success_values,
)
from app.services.payment_events import record_payment_event_best_effort
from app.services.paypal import (
    PayPalApiError,
    paypal_create_order,
    paypal_get_order,
    paypal_is_configured,
    paypal_void_order,
)
from app.services.pricing import apply_percent_discount, get_bouquet_discount
from app.services.settings import get_store_settings

router = APIRouter(prefix="/api/checkout", tags=["checkout"])
FLOWER_QUANTITY_MIN = 1
FLOWER_QUANTITY_MAX = 1001
STANDARD_PRODUCT_QUANTITY_MAX = 25
CUSTOM_PRODUCT_QUANTITY_MAX = 10
MAX_CHECKOUT_TOTAL_CENTS = 10_000_000
FLORIST_CHOICE_NAME = "Florist Choice Bouquet"
FLORIST_CHOICE_IMAGE = "/images/florist-choice.webp"
FLORIST_CHOICE_ID_PREFIX = "florist-choice-"
DELIVERY_TIME_WINDOWS = {"8:30 AM - 12 PM", "12 PM - 4 PM", "4 PM - 8 PM"}
checkout_limiter = SlidingWindowRateLimiter(limit=10, window_seconds=15 * 60)


def _is_flower_quantity_enabled_for_bouquet(bouquet: Bouquet) -> bool:
    bouquet_type = str(getattr(bouquet, "bouquet_type", "") or "").strip().upper()
    if bouquet_type not in {BouquetType.MONO.value, BouquetType.SEASON.value}:
        return False
    return bool(getattr(bouquet, "allow_flower_quantity", False))


def _set_order_status_safely(db: Session, order: Order, status: OrderStatus) -> None:
    try:
        if status == OrderStatus.PAID:
            values = payment_success_values()
        else:
            values = {"status": status}
        for key, value in values.items():
            setattr(order, key, value)
        db.commit()
    except Exception:
        db.rollback()


def _set_order_failed_safely(
    db: Session,
    order: Order,
    *,
    diagnostics,
) -> None:
    try:
        values = payment_failure_values(diagnostics)
        for key, value in values.items():
            setattr(order, key, value)
        db.commit()
    except Exception:
        db.rollback()


def _order_email(order: Order) -> str:
    return (order.email or "").strip().lower()


def _normalize_payment_method(value: str | None) -> str:
    normalized = (value or "").strip().lower().replace("-", "_")
    if not normalized:
        return "stripe"

    aliases = {
        "card": "stripe",
        "credit": "stripe",
        "credit_card": "stripe",
        "stripe_card": "stripe",
        "pay_pal": "paypal",
        "paypal_checkout": "paypal",
    }
    return aliases.get(normalized, normalized)


def _payment_provider_for_order(order: Order, raw_provider: str | None = None) -> str:
    if raw_provider:
        normalized = _normalize_payment_method(raw_provider)
        if normalized in {"stripe", "paypal"}:
            return normalized
    if order.stripe_session_id:
        return "stripe"
    if order.paypal_order_id:
        return "paypal"
    return "checkout"


CLIENT_CHECKOUT_EVENTS = {
    "browser_redirect_started",
    "browser_success_returned",
    "browser_cancel_returned",
    "browser_status_check_started",
}


def _clean_text(value: str | None) -> str:
    return (value or "").strip()


def _safe_checkout_event_context(context: dict | None) -> dict[str, str | int | float | bool]:
    """Keep browser telemetry bounded and free from nested sensitive blobs."""
    safe: dict[str, str | int | float | bool] = {}
    for raw_key, raw_value in (context or {}).items():
        key = str(raw_key).strip()
        if not key or len(key) > 64:
            continue
        if isinstance(raw_value, str):
            safe[key] = raw_value.strip()[:256]
        elif isinstance(raw_value, bool):
            safe[key] = raw_value
        elif isinstance(raw_value, (int, float)):
            safe[key] = raw_value
    return safe


def _add_one_month(value: date) -> date:
    month = value.month + 1
    year = value.year
    if month > 12:
        month = 1
        year += 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _validate_delivery_date_time(value: str) -> bool:
    trimmed = _clean_text(value)
    if not trimmed:
        return False

    try:
        parsed = json.loads(trimmed)
    except json.JSONDecodeError:
        try:
            datetime.fromisoformat(trimmed)
        except ValueError:
            return False
        return "T" in trimmed

    if not isinstance(parsed, dict):
        return False

    raw_date = parsed.get("date")
    raw_window = parsed.get("timeWindow")
    raw_ideal_time = parsed.get("idealTime")
    delivery_date = raw_date.strip() if isinstance(raw_date, str) else ""
    time_window = raw_window.strip() if isinstance(raw_window, str) else ""
    ideal_time = raw_ideal_time.strip() if isinstance(raw_ideal_time, str) else ""

    try:
        parsed_date = date.fromisoformat(delivery_date)
    except ValueError:
        return False

    today = date.today()
    if parsed_date < today or parsed_date > _add_one_month(today):
        return False

    if time_window not in DELIVERY_TIME_WINDOWS:
        return False

    if not ideal_time:
        return False

    normalized_ideal_time = ideal_time.upper().replace(" ", "")
    try:
        parsed_ideal_time = datetime.strptime(normalized_ideal_time, "%I:%M%p").time()
    except ValueError:
        return False
    ideal_minutes = parsed_ideal_time.hour * 60 + parsed_ideal_time.minute
    if ideal_minutes < 8 * 60 or ideal_minutes > 20 * 60:
        return False

    return True


def _format_delivery_address(
    *,
    line1: str,
    line2: str,
    floor: str,
    city: str,
    state: str,
    postal_code: str,
    country: str,
) -> str:
    base = line1.strip()
    extras = []
    if line2 and line2.strip():
        extras.append(line2.strip())
    if floor and floor.strip():
        cleaned_floor = floor.strip()
        if cleaned_floor.lower().startswith("floor"):
            extras.append(cleaned_floor)
        else:
            extras.append(f"Floor {cleaned_floor}")
    if extras:
        base = f"{base}, {', '.join(extras)}"

    state_zip = " ".join(part for part in [state.strip(), postal_code.strip()] if part)
    city_state_zip = ", ".join(part for part in [city.strip(), state_zip] if part)
    parts = [base, city_state_zip, country.strip()]
    return ", ".join(part for part in parts if part)


def _absolute_image_url(origin: str, image: str | None) -> str | None:
    value = (image or "").strip()
    if not value:
        return None
    if value.startswith(("http://", "https://")):
        return value
    return f"{origin}{value}"


def _set_checkout_access_cookie(response: Response, order_id: str) -> None:
    response.set_cookie(
        key=checkout_access_cookie_name(order_id),
        value=create_checkout_access_token(order_id=order_id),
        httponly=True,
        secure=settings.is_production(),
        samesite="lax",
        path="/",
        max_age=CHECKOUT_ACCESS_TOKEN_TTL_HOURS * 60 * 60,
    )


def _is_order_access_allowed(order: Order, *, user, request: Request) -> bool:
    order_email = _order_email(order)
    if not order_email:
        return False

    user_email = (getattr(user, "email", None) or "").strip().lower()
    if user_email and user_email == order_email:
        return True

    try:
        token_value = request.cookies.get(checkout_access_cookie_name(order.id), "").strip()
    except ValueError:
        return False
    if not token_value:
        return False

    _reject_cross_site_cookie_request(request)

    try:
        token_payload = decode_checkout_access_token(token_value)
    except Exception:
        return False

    token_order_id = str(token_payload.get("order_id") or "").strip()
    return token_order_id == order.id


def _resolve_first_order_discount_percent(
    *,
    configured_percent: int | None,
    has_blocking_order_history: bool,
    has_any_discount: bool,
) -> int:
    percent = int(configured_percent or 0)
    if percent <= 0:
        return 0
    if has_blocking_order_history:
        return 0
    if has_any_discount:
        return 0
    return percent


@router.post("", response_model=CheckoutResponse)
async def start_checkout(
    payload: CheckoutRequest,
    request: Request,
    response: Response,
    user=Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    enforce_rate_limit(request, checkout_limiter, detail="Too many checkout attempts. Please try again shortly.")
    user_id = user.id if user else None

    raw_payment_method = payload.payment_method
    payment_method = _normalize_payment_method(raw_payment_method)
    if payment_method not in {"stripe", "paypal"}:
        log_critical_event(
            domain="payment",
            event="checkout_invalid_payment_method",
            message="Checkout requested with unsupported payment method.",
            request=request,
            context={
                "user_id": user_id,
                "payment_method": payment_method,
                "raw_payment_method": (raw_payment_method or "").strip(),
            },
            level=logging.WARNING,
        )
        raise HTTPException(status_code=400, detail="Unsupported payment method.")

    if payment_method == "stripe":
        if not settings.stripe_secret_key:
            log_critical_event(
                domain="payment",
                event="stripe_not_configured",
                message="Checkout requested while Stripe is not configured.",
                request=request,
                context={"user_id": user_id},
            )
            raise HTTPException(status_code=400, detail="Stripe is not configured.")
    else:
        if not paypal_is_configured():
            log_critical_event(
                domain="payment",
                event="paypal_not_configured",
                message="Checkout requested while PayPal is not configured.",
                request=request,
                context={"user_id": user_id},
            )
            raise HTTPException(status_code=400, detail="PayPal is not configured.")

    items = payload.items
    raw_address = _clean_text(payload.address)
    address_line1 = _clean_text(payload.address_line1)
    address_line2 = _clean_text(payload.address_line2)
    city = _clean_text(payload.city)
    state = _clean_text(payload.state)
    postal_code = _clean_text(payload.postal_code)
    country = _clean_text(payload.country) or "United States"
    floor = _clean_text(payload.floor)
    delivery_date_time = _clean_text(payload.delivery_date_time)
    order_comment = _clean_text(payload.order_comment)
    raw_phone = _clean_text(payload.phone)
    payload_email = _clean_text(payload.email).lower()
    has_structured_address = any(
        [address_line1, address_line2, city, state, postal_code, floor]
    )
    if not has_structured_address:
        country = ""
    checkout_email = (user.email or "").strip().lower() if user else payload_email
    fallback_phone = (user.phone or "").strip() if user else ""
    phone_candidate = raw_phone or fallback_phone
    digits = "".join(char for char in phone_candidate if char.isdigit())
    normalized_phone = (
        f"+{digits}" if len(digits) == 11 and digits.startswith("1") else ""
    )

    if not items:
        log_critical_event(
            domain="cart",
            event="checkout_empty_cart",
            message="Checkout request contains no items.",
            request=request,
            context={"user_id": user_id},
            level=logging.WARNING,
        )
        raise HTTPException(status_code=400, detail="No items provided.")
    if "@" not in checkout_email:
        log_critical_event(
            domain="personal_data",
            event="checkout_missing_or_invalid_email",
            message="Checkout request has missing or invalid email.",
            request=request,
            context={"user_id": user_id},
            level=logging.WARNING,
        )
        raise HTTPException(status_code=400, detail="A valid email is required.")
    address_for_quote = raw_address
    if not address_for_quote:
        if not address_line1 or not city or not state or not postal_code:
            log_critical_event(
                domain="personal_data",
                event="checkout_missing_address",
                message="Checkout request has incomplete delivery address.",
                request=request,
                context={"user_id": user_id},
                level=logging.WARNING,
            )
            raise HTTPException(
                status_code=400,
                detail="Delivery address must include street, city, state, and ZIP.",
            )
        address_for_quote = _format_delivery_address(
            line1=address_line1,
            line2="",
            floor="",
            city=city,
            state=state,
            postal_code=postal_code,
            country=country,
        )

    if order_comment and len(order_comment) > 500:
        log_critical_event(
            domain="cart",
            event="checkout_order_comment_too_long",
            message="Checkout request contains an order comment that is too long.",
            request=request,
            context={
                "user_id": user_id,
                "order_comment_length": len(order_comment),
            },
            level=logging.WARNING,
        )
        raise HTTPException(status_code=400, detail="Order comment is too long.")
    if not delivery_date_time:
        log_critical_event(
            domain="cart",
            event="checkout_missing_delivery_datetime",
            message="Checkout request is missing the requested delivery date/time.",
            request=request,
            context={"user_id": user_id},
            level=logging.WARNING,
        )
        raise HTTPException(
            status_code=400,
            detail="Delivery date and time is required.",
        )
    if len(delivery_date_time) > 160:
        log_critical_event(
            domain="cart",
            event="checkout_delivery_datetime_too_long",
            message="Checkout request contains a delivery date/time that is too long.",
            request=request,
            context={
                "user_id": user_id,
                "delivery_date_time_length": len(delivery_date_time),
            },
            level=logging.WARNING,
        )
        raise HTTPException(status_code=400, detail="Delivery date/time is too long.")
    if not _validate_delivery_date_time(delivery_date_time):
        log_critical_event(
            domain="cart",
            event="checkout_delivery_datetime_invalid",
            message="Checkout request contains an invalid delivery date/time.",
            request=request,
            context={"user_id": user_id},
            level=logging.WARNING,
        )
        raise HTTPException(
            status_code=400,
            detail="Delivery date and time is invalid.",
        )
    if payment_method == "stripe" and not normalized_phone:
        log_critical_event(
            domain="personal_data",
            event="checkout_invalid_phone",
            message="Stripe checkout request has invalid phone format.",
            request=request,
            context={"user_id": user_id, "phone_length": len(phone_candidate)},
            level=logging.WARNING,
        )
        raise HTTPException(status_code=400, detail="Use phone format +1 312 555 0123.")

    settings_row = get_store_settings(db)
    delivery = await get_delivery_quote(address_for_quote)
    if not delivery.ok:
        delivery_context = build_delivery_quote_log_context(address_for_quote, delivery)
        delivery_context.update({"user_id": user_id, "item_count": len(items)})
        log_critical_event(
            domain="payment",
            event="delivery_quote_failed",
            message="Delivery quote failed during checkout.",
            request=request,
            context=delivery_context,
            level=delivery_quote_failure_level(delivery),
        )
        raise HTTPException(
            status_code=400, detail=delivery.error or "Unable to calculate delivery."
        )

    bouquet_ids = [item.id for item in items if not item.is_custom]
    bouquets = (
        db.execute(
            select(Bouquet).where(
                Bouquet.id.in_(bouquet_ids),
                Bouquet.is_active.is_(True),
                Bouquet.is_sold_out.is_(False),
            )
        )
        .scalars()
        .all()
    )
    bouquet_map = {bouquet.id: bouquet for bouquet in bouquets}

    has_any_discount = False
    normalized_items = []

    for item in items:
        if item.is_custom:
            price_cents = int(item.price_cents or 0)
            quantity = item.quantity
            details = _clean_text(item.details)
            if details and len(details) > 500:
                log_critical_event(
                    domain="cart",
                    event="checkout_custom_item_details_too_long",
                    message="Custom cart item details are too long.",
                    request=request,
                    context={
                        "user_id": user_id,
                        "item_id": item.id,
                        "details_length": len(details),
                    },
                    level=logging.WARNING,
                )
                raise HTTPException(
                    status_code=400, detail="Custom item details are too long."
                )
            if (
                not item.id.startswith(FLORIST_CHOICE_ID_PREFIX)
                or item.name != FLORIST_CHOICE_NAME
                or item.image != FLORIST_CHOICE_IMAGE
            ):
                log_critical_event(
                    domain="cart",
                    event="invalid_custom_item_payload",
                    message="Custom cart item does not match the supported florist-choice product.",
                    request=request,
                    context={"user_id": user_id, "item_id": item.id},
                    level=logging.WARNING,
                )
                raise HTTPException(
                    status_code=400, detail="Some items are unavailable."
                )
            if (
                price_cents < 6500
                or price_cents > 18000
                or price_cents % 500 != 0
                or quantity > CUSTOM_PRODUCT_QUANTITY_MAX
            ):
                log_critical_event(
                    domain="cart",
                    event="invalid_custom_item_price",
                    message="Custom cart item price is out of expected range.",
                    request=request,
                    context={
                        "user_id": user_id,
                        "item_id": item.id,
                        "price_cents": price_cents,
                    },
                    level=logging.WARNING,
                )
                raise HTTPException(
                    status_code=400, detail="Some items are unavailable."
                )
            normalized_items.append(
                {
                    "id": item.id,
                    "bouquet_id": None,
                    "name": FLORIST_CHOICE_NAME,
                    "image": FLORIST_CHOICE_IMAGE,
                    "quantity": quantity,
                    "unit_price": price_cents,
                    "details": details or None,
                }
            )
            continue

        bouquet = bouquet_map.get(item.id)
        if not bouquet:
            log_critical_event(
                domain="cart",
                event="checkout_item_not_found",
                message="Checkout item does not exist, is inactive, or is sold out.",
                request=request,
                context={"user_id": user_id, "item_id": item.id},
                level=logging.WARNING,
            )
            raise HTTPException(status_code=400, detail="Some items are unavailable.")
        catalog_type = getattr(bouquet, "catalog_type", CatalogType.FLOWERS)
        if catalog_type == CatalogType.EVENT_SPACE or str(catalog_type).upper() == "EVENT_SPACE":
            log_critical_event(
                domain="payment",
                event="checkout_event_space_rejected",
                message="Event Space products must not enter the payment checkout flow.",
                request=request,
                context={"user_id": user_id, "item_id": item.id},
                level=logging.WARNING,
            )
            raise HTTPException(status_code=400, detail="Event Space bookings are requested separately.")
        discount = get_bouquet_discount(bouquet, settings_row)
        if discount:
            has_any_discount = True
        unit_price = (
            apply_percent_discount(bouquet.price_cents, discount.percent)
            if discount
            else bouquet.price_cents
        )
        has_flower_quantity = _is_flower_quantity_enabled_for_bouquet(bouquet)
        raw_quantity = item.quantity
        quantity = raw_quantity
        details = None
        if has_flower_quantity:
            if raw_quantity < FLOWER_QUANTITY_MIN or raw_quantity > FLOWER_QUANTITY_MAX:
                log_critical_event(
                    domain="cart",
                    event="checkout_flower_quantity_out_of_range",
                    message="Checkout flower quantity is outside the allowed range.",
                    request=request,
                    context={
                        "user_id": user_id,
                        "item_id": item.id,
                        "flower_quantity": raw_quantity,
                        "min_quantity": FLOWER_QUANTITY_MIN,
                        "max_quantity": FLOWER_QUANTITY_MAX,
                    },
                    level=logging.WARNING,
                )
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Flower quantity must be between "
                        f"{FLOWER_QUANTITY_MIN} and {FLOWER_QUANTITY_MAX}."
                    ),
                )
            quantity = raw_quantity
            details = f"Flowers: {quantity}"
        elif raw_quantity > STANDARD_PRODUCT_QUANTITY_MAX:
            log_critical_event(
                domain="cart",
                event="checkout_product_quantity_out_of_range",
                message="Checkout product quantity is outside the allowed range.",
                request=request,
                context={
                    "user_id": user_id,
                    "item_id": item.id,
                    "quantity": raw_quantity,
                    "max_quantity": STANDARD_PRODUCT_QUANTITY_MAX,
                },
                level=logging.WARNING,
            )
            raise HTTPException(
                status_code=400,
                detail=f"Product quantity must be at most {STANDARD_PRODUCT_QUANTITY_MAX}.",
            )
        normalized_items.append(
            {
                "id": bouquet.id,
                "bouquet_id": bouquet.id,
                "name": bouquet.name,
                "image": bouquet.image,
                "quantity": quantity,
                "unit_price": unit_price,
                "details": details,
            }
        )

    # Only explicit final failures may reopen first-order discount eligibility.
    # Pending orders remain blocking so delayed provider updates cannot reopen
    # the discount and create a second discounted checkout.
    expire_pending_orders(db)

    if user:
        # Serialize first-order-discount calculation for authenticated users.
        db.execute(select(User.id).where(User.id == user.id).with_for_update()).first()

    has_blocking_order_history = (
        db.execute(
            select(Order.id)
            .where(
                Order.email == checkout_email,
                Order.status.in_([OrderStatus.PENDING, OrderStatus.PAID]),
            )
            .limit(1)
        )
        .scalars()
        .first()
        is not None
    )
    # A guest can claim arbitrary email addresses and cannot be serialized
    # across concurrent browser sessions.  Limit this one-time promotion to a
    # verified account, where the user-row lock above makes it race-safe.
    first_order_discount_percent = (
        _resolve_first_order_discount_percent(
            configured_percent=settings_row.first_order_discount_percent,
            has_blocking_order_history=has_blocking_order_history,
            has_any_discount=has_any_discount,
        )
        if user
        else 0
    )

    discounted_items = []
    for item in normalized_items:
        unit_price = (
            apply_percent_discount(item["unit_price"], first_order_discount_percent)
            if first_order_discount_percent > 0
            else item["unit_price"]
        )
        discounted_items.append({**item, "unit_price": unit_price})

    discounted_subtotal = sum(
        item["unit_price"] * item["quantity"] for item in discounted_items
    )
    computed_total = discounted_subtotal + (delivery.fee_cents or 0)
    if computed_total <= 0 or computed_total > MAX_CHECKOUT_TOTAL_CENTS:
        log_critical_event(
            domain="payment",
            event="checkout_total_out_of_range",
            message="Server-calculated checkout total is outside the allowed range.",
            request=request,
            context={"user_id": user_id, "total_cents": computed_total},
            level=logging.WARNING,
        )
        raise HTTPException(status_code=400, detail="Checkout total is invalid.")

    order_items = [
        OrderItem(
            bouquet_id=item.get("bouquet_id"),
            name=item["name"],
            price_cents=item["unit_price"],
            quantity=item["quantity"],
            image=item["image"],
            details=item.get("details"),
        )
        for item in discounted_items
    ]

    if delivery.fee_cents and delivery.fee_cents > 0:
        order_items.append(
            OrderItem(
                name=f"Delivery ({delivery.distance_text})",
                price_cents=delivery.fee_cents,
                quantity=1,
                image="",
            )
        )

    delivery_address = address_for_quote
    if address_line1:
        delivery_address = _format_delivery_address(
            line1=address_line1,
            line2=address_line2,
            floor=floor,
            city=city,
            state=state,
            postal_code=postal_code,
            country=country,
        )

    order = Order(
        email=checkout_email,
        phone=normalized_phone or None,
        total_cents=computed_total,
        items=order_items,
        delivery_address=delivery_address or None,
        delivery_address_line1=address_line1 or None,
        delivery_address_line2=address_line2 or None,
        delivery_city=city or None,
        delivery_state=state or None,
        delivery_postal_code=postal_code or None,
        delivery_country=country or None,
        delivery_floor=floor or None,
        delivery_date_time=delivery_date_time or None,
        order_comment=order_comment or None,
        delivery_miles=f"{delivery.miles:.1f}" if delivery.miles is not None else None,
        delivery_fee_cents=delivery.fee_cents,
        first_order_discount_percent=first_order_discount_percent,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    if user and normalized_phone and user.phone != normalized_phone:
        user.phone = normalized_phone
        db.commit()

    origin = settings.resolved_site_url()
    encoded_order_id = quote_plus(order.id)

    record_payment_event_best_effort(
        db,
        order_id=order.id,
        event="checkout_order_created",
        provider=payment_method,
        source="server",
        message="Checkout order was created and is waiting for provider session setup.",
        context={
            "order_status": order.status.value,
            "total_cents": computed_total,
            "currency": order.currency,
            "item_count": len(discounted_items),
            "has_delivery_fee": bool(delivery.fee_cents and delivery.fee_cents > 0),
            "delivery_fee_cents": delivery.fee_cents or 0,
        },
        request=request,
    )

    if payment_method == "paypal":
        try:
            paypal_order = paypal_create_order(
                order_id=order.id,
                total_cents=computed_total,
                currency=order.currency,
                payer_email=checkout_email,
                payer_name=(user.name if user else None),
                return_url=(
                    f"{origin}/checkout/success?provider=paypal&orderId={encoded_order_id}"
                ),
                cancel_url=(
                    f"{origin}/cart?checkoutCanceled=1&orderId={encoded_order_id}"
                    f"&provider=paypal"
                ),
            )
        except PayPalApiError as exc:
            log_critical_event(
                domain="payment",
                event="paypal_order_create_failed",
                message="PayPal order creation failed.",
                request=request,
                context={
                    "order_id": order.id,
                    "user_id": user_id,
                    "item_count": len(discounted_items),
                },
                exc=exc,
            )
            _set_order_failed_safely(
                db,
                order,
                diagnostics=build_exception_failure_diagnostics(
                    stage="paypal_order_create",
                    code="paypal_order_create_failed",
                    message="Failed to create the PayPal order.",
                    exc=exc,
                    provider="paypal",
                ),
            )
            record_payment_event_best_effort(
                db,
                order_id=order.id,
                event="paypal_order_create_failed",
                provider="paypal",
                source="server",
                message="PayPal order creation failed before customer approval.",
                context={"order_status": OrderStatus.FAILED.value},
                request=request,
            )
            raise HTTPException(status_code=502, detail="Unable to start checkout.")

        order.paypal_order_id = paypal_order.order_id
        db.commit()
        _set_checkout_access_cookie(response, order.id)
        record_payment_event_best_effort(
            db,
            order_id=order.id,
            event="paypal_order_created",
            provider="paypal",
            source="server",
            message="PayPal order was created and approval URL was returned.",
            context={"paypal_order_id": paypal_order.order_id},
            request=request,
        )
        return CheckoutResponse(
            url=paypal_order.approve_url,
            order_id=order.id,
            provider="paypal",
        )

    stripe.api_key = settings.stripe_secret_key
    expires_at = (
        int(datetime.now(timezone.utc).timestamp())
        + STRIPE_CHECKOUT_SESSION_EXPIRATION_SECONDS
    )

    line_items = [
        {
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": item["name"],
                    "images": (
                        [image_url]
                        if (image_url := _absolute_image_url(origin, item["image"]))
                        else []
                    ),
                },
                "unit_amount": item["unit_price"],
            },
            "quantity": item["quantity"],
        }
        for item in discounted_items
    ]

    if delivery.fee_cents and delivery.fee_cents > 0:
        line_items.append(
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": "Delivery", "images": []},
                    "unit_amount": delivery.fee_cents,
                },
                "quantity": 1,
            }
        )

    record_payment_event_best_effort(
        db,
        order_id=order.id,
        event="stripe_checkout_create_started",
        provider="stripe",
        source="server",
        message="Stripe Checkout session creation started.",
        context={
            "expires_at": expires_at,
            "line_item_count": len(line_items),
            "total_cents": computed_total,
            "currency": order.currency,
        },
        request=request,
    )

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=line_items,
            success_url=(
                f"{origin}/checkout/success?provider=stripe&orderId={encoded_order_id}"
            ),
            cancel_url=(
                f"{origin}/cart?checkoutCanceled=1&orderId={encoded_order_id}"
                f"&provider=stripe"
            ),
            payment_method_types=["card"],
            customer_email=checkout_email or None,
            expires_at=expires_at,
            metadata={
                "orderId": order.id,
                "deliveryAddress": delivery_address or address_for_quote,
                "deliveryAddressLine1": address_line1 or "",
                "deliveryAddressLine2": address_line2 or "",
                "deliveryCity": city or "",
                "deliveryState": state or "",
                "deliveryPostalCode": postal_code or "",
                "deliveryCountry": country or "",
                "deliveryFloor": floor or "",
                "deliveryDateTime": delivery_date_time or "",
                "deliveryMiles": (
                    f"{delivery.miles:.1f}" if delivery.miles is not None else ""
                ),
                "deliveryFeeCents": str(delivery.fee_cents or 0),
                "firstOrderDiscountPercent": str(first_order_discount_percent),
                "phone": normalized_phone,
                "orderComment": order_comment or "",
            },
            payment_intent_data={"metadata": {"orderId": order.id}},
            idempotency_key=f"stripe-checkout-{order.id}",
        )
    except Exception as exc:
        log_critical_event(
            domain="payment",
            event="stripe_checkout_session_failed",
            message="Stripe checkout session creation failed.",
            request=request,
            context={
                "order_id": order.id,
                "user_id": user_id,
                "item_count": len(discounted_items),
            },
            exc=exc,
        )
        _set_order_failed_safely(
            db,
            order,
            diagnostics=build_exception_failure_diagnostics(
                stage="stripe_checkout_create",
                code="stripe_checkout_session_failed",
                message="Failed to create the Stripe Checkout session.",
                exc=exc,
                provider="stripe",
            ),
        )
        record_payment_event_best_effort(
            db,
            order_id=order.id,
            event="stripe_checkout_create_failed",
            provider="stripe",
            source="server",
            message="Stripe Checkout session creation failed.",
            context={"order_status": OrderStatus.FAILED.value},
            request=request,
        )
        raise HTTPException(status_code=502, detail="Unable to start checkout.")

    order.stripe_session_id = session.id
    db.commit()
    record_payment_event_best_effort(
        db,
        order_id=order.id,
        event="stripe_checkout_session_created",
        provider="stripe",
        source="server",
        message="Stripe Checkout session was created and redirect URL is available.",
        stripe_session_id=session.id,
        payment_intent_id=getattr(session, "payment_intent", None),
        context={
            "session_status": getattr(session, "status", None),
            "payment_status": getattr(session, "payment_status", None),
            "expires_at": getattr(session, "expires_at", expires_at),
        },
        request=request,
    )

    if not session.url:
        log_critical_event(
            domain="payment",
            event="stripe_session_missing_url",
            message="Stripe session was created without redirect URL.",
            request=request,
            context={"order_id": order.id, "user_id": user_id},
        )
        _set_order_failed_safely(
            db,
            order,
            diagnostics=build_exception_failure_diagnostics(
                stage="stripe_checkout_redirect",
                code="stripe_session_missing_url",
                message="Stripe created a checkout session without a redirect URL.",
                provider="stripe",
                extra_details={"Session ID": session.id},
            ),
        )
        record_payment_event_best_effort(
            db,
            order_id=order.id,
            event="stripe_checkout_redirect_url_missing",
            provider="stripe",
            source="server",
            message="Stripe created a Checkout session without a redirect URL.",
            stripe_session_id=session.id,
            context={"order_status": OrderStatus.FAILED.value},
            request=request,
        )
        raise HTTPException(status_code=500, detail="Unable to start checkout.")
    _set_checkout_access_cookie(response, order.id)
    return CheckoutResponse(
        url=session.url,
        order_id=order.id,
        provider="stripe",
    )


@router.post("/event", response_model=CheckoutEventResponse)
async def record_checkout_event(
    payload: CheckoutEventRequest,
    request: Request,
    user=Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    event_name = _clean_text(payload.event).lower()
    if event_name not in CLIENT_CHECKOUT_EVENTS:
        log_critical_event(
            domain="payment",
            event="checkout_client_event_invalid",
            message="Checkout client event was rejected: unsupported event name.",
            request=request,
            context={"event_name": event_name},
            level=logging.WARNING,
        )
        raise HTTPException(status_code=400, detail="Unsupported checkout event.")

    order = db.get(Order, payload.order_id)
    if not order:
        log_critical_event(
            domain="payment",
            event="checkout_client_event_order_not_found",
            message="Checkout client event references a missing order.",
            request=request,
            context={"order_id": payload.order_id, "event_name": event_name},
            level=logging.WARNING,
        )
        raise HTTPException(status_code=404, detail="Not found")

    if not _is_order_access_allowed(order, user=user, request=request):
        log_critical_event(
            domain="payment",
            event="checkout_client_event_unauthorized",
            message="Checkout client event denied: invalid user/token for order.",
            request=request,
            context={"order_id": order.id, "event_name": event_name},
            level=logging.WARNING,
        )
        raise HTTPException(status_code=404, detail="Not found")

    provider = _payment_provider_for_order(order, payload.provider)
    event_context = {
        **_safe_checkout_event_context(payload.context),
        "order_status": order.status.value,
        "client_event": event_name,
    }
    record_payment_event_best_effort(
        db,
        order_id=order.id,
        event=event_name,
        provider=provider,
        source="browser",
        message="Browser reported a checkout flow event.",
        stripe_session_id=order.stripe_session_id,
        context=event_context,
        request=request,
    )
    return CheckoutEventResponse(received=True)


@router.post("/cancel", response_model=CheckoutCancelResponse)
async def cancel_checkout(
    payload: CheckoutCancelRequest,
    request: Request,
    user=Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    user_id = user.id if user else None

    order_id = (payload.order_id or "").strip()
    paypal_order_id = (payload.paypal_order_id or "").strip()
    order = db.get(Order, order_id) if order_id else None
    if not order and paypal_order_id:
        order = (
            db.execute(select(Order).where(Order.paypal_order_id == paypal_order_id))
            .scalars()
            .first()
        )
    if not order:
        log_critical_event(
            domain="payment",
            event="checkout_cancel_order_not_found",
            message="Checkout cancel requested for a missing order.",
            request=request,
            context={
                "order_id": order_id or None,
                "paypal_order_id": paypal_order_id or None,
                "user_id": user_id,
            },
            level=logging.WARNING,
        )
        raise HTTPException(status_code=404, detail="Not found")
    access_allowed = _is_order_access_allowed(order, user=user, request=request)
    if not access_allowed:
        log_critical_event(
            domain="payment",
            event="checkout_cancel_unauthorized",
            message="Checkout cancel denied: invalid user/token for order.",
            request=request,
            context={
                "order_id": order_id or order.id,
                "paypal_order_id": paypal_order_id or order.paypal_order_id,
                "user_id": user_id,
            },
            level=logging.WARNING,
        )
        raise HTTPException(status_code=404, detail="Not found")

    provider = _payment_provider_for_order(order, "paypal" if paypal_order_id else None)
    record_payment_event_best_effort(
        db,
        order_id=order.id,
        event="checkout_cancel_returned",
        provider=provider,
        source="server",
        message="Customer returned to the cart through the checkout cancel flow.",
        stripe_session_id=order.stripe_session_id,
        context={
            "order_status_before": order.status.value,
            "has_checkout_access_cookie": bool(
                request.cookies.get(checkout_access_cookie_name(order.id))
            ),
            "has_paypal_order_token": bool(paypal_order_id),
        },
        request=request,
    )

    if order.status == OrderStatus.PAID:
        record_payment_event_best_effort(
            db,
            order_id=order.id,
            event="checkout_cancel_observed_paid",
            provider=provider,
            source="server",
            message="Cancel flow found that the order was already paid.",
            stripe_session_id=order.stripe_session_id,
            context={"order_status": order.status.value},
            request=request,
        )
        return CheckoutCancelResponse(canceled=False, status=order.status.value)

    if order.status in {OrderStatus.CANCELED, OrderStatus.FAILED}:
        record_payment_event_best_effort(
            db,
            order_id=order.id,
            event="checkout_cancel_observed_closed",
            provider=provider,
            source="server",
            message="Cancel flow found that the order was already closed.",
            stripe_session_id=order.stripe_session_id,
            context={"order_status": order.status.value},
            request=request,
        )
        return CheckoutCancelResponse(canceled=True, status=order.status.value)

    stripe_cancel_confirmed: bool | None = None
    if order.stripe_session_id:
        stripe_cancel_confirmed = False
    if order.stripe_session_id and settings.stripe_secret_key:
        stripe.api_key = settings.stripe_secret_key
        try:
            session = stripe.checkout.Session.retrieve(order.stripe_session_id)
        except Exception as exc:
            log_critical_event(
                domain="payment",
                event="stripe_session_fetch_failed_during_cancel",
                message="Failed to fetch Stripe checkout session during cancellation.",
                request=request,
                context={"order_id": order.id, "user_id": user_id},
                exc=exc,
                level=logging.WARNING,
            )
            record_payment_event_best_effort(
                db,
                order_id=order.id,
                event="stripe_session_fetch_failed_during_cancel",
                provider="stripe",
                source="server",
                message="Failed to fetch Stripe Checkout session during cancel flow.",
                stripe_session_id=order.stripe_session_id,
                context={"order_status": order.status.value},
                request=request,
            )
            session = None

        if session:
            resolved_status = resolve_order_status_from_session(order, session)
            if resolved_status == OrderStatus.PAID:
                _set_order_status_safely(db, order, OrderStatus.PAID)
                record_payment_event_best_effort(
                    db,
                    order_id=order.id,
                    event="checkout_cancel_resolved_paid",
                    provider="stripe",
                    source="server",
                    message="Cancel flow synced Stripe session and resolved the order as paid.",
                    stripe_session_id=order.stripe_session_id,
                    payment_intent_id=getattr(session, "payment_intent", None),
                    context={
                        "session_status": getattr(session, "status", None),
                        "payment_status": getattr(session, "payment_status", None),
                    },
                    request=request,
                )
                return CheckoutCancelResponse(
                    canceled=False, status=OrderStatus.PAID.value
                )
            if resolved_status == OrderStatus.FAILED:
                _set_order_failed_safely(
                    db,
                    order,
                    diagnostics=build_stripe_session_failure_diagnostics(session),
                )
                record_payment_event_best_effort(
                    db,
                    order_id=order.id,
                    event="checkout_cancel_resolved_failed",
                    provider="stripe",
                    source="server",
                    message="Cancel flow synced Stripe session and resolved the order as failed.",
                    stripe_session_id=order.stripe_session_id,
                    payment_intent_id=getattr(session, "payment_intent", None),
                    context={
                        "session_status": getattr(session, "status", None),
                        "payment_status": getattr(session, "payment_status", None),
                    },
                    request=request,
                )
                return CheckoutCancelResponse(
                    canceled=True, status=OrderStatus.FAILED.value
                )

            session_status = (getattr(session, "status", None) or "").lower()
            if session_status == "open":
                try:
                    stripe.checkout.Session.expire(order.stripe_session_id)
                    stripe_cancel_confirmed = True
                    record_payment_event_best_effort(
                        db,
                        order_id=order.id,
                        event="stripe_session_expired_by_cancel",
                        provider="stripe",
                        source="server",
                        message="Open Stripe Checkout session was expired after customer cancel return.",
                        stripe_session_id=order.stripe_session_id,
                        context={"session_status_before": session_status},
                        request=request,
                    )
                except Exception as exc:
                    log_critical_event(
                        domain="payment",
                        event="stripe_session_expire_failed",
                        message="Failed to expire open Stripe checkout session during cancellation.",
                        request=request,
                        context={"order_id": order.id, "user_id": user_id},
                        exc=exc,
                        level=logging.WARNING,
                    )
                    record_payment_event_best_effort(
                        db,
                        order_id=order.id,
                        event="stripe_session_expire_failed",
                        provider="stripe",
                        source="server",
                        message="Failed to expire open Stripe Checkout session during cancel flow.",
                        stripe_session_id=order.stripe_session_id,
                        context={"session_status_before": session_status},
                        request=request,
                    )

    paypal_cancel_confirmed: bool | None = None
    if order.paypal_order_id:
        paypal_cancel_confirmed = False
    if order.paypal_order_id and paypal_is_configured():
        paypal_order_payload = None
        try:
            paypal_order_payload = paypal_get_order(order.paypal_order_id)
        except PayPalApiError as exc:
            log_critical_event(
                domain="payment",
                event="paypal_order_fetch_failed_during_cancel",
                message="Failed to fetch PayPal order during cancellation.",
                request=request,
                context={"order_id": order.id, "user_id": user_id},
                exc=exc,
                level=logging.WARNING,
            )
            record_payment_event_best_effort(
                db,
                order_id=order.id,
                event="paypal_order_fetch_failed_during_cancel",
                provider="paypal",
                source="server",
                message="Failed to fetch PayPal order during cancel flow.",
                context={"paypal_order_id": order.paypal_order_id},
                request=request,
            )
        if paypal_order_payload:
            resolved_status, _capture_id = resolve_order_status_from_paypal_order(
                order, paypal_order_payload
            )
            if resolved_status == OrderStatus.PAID:
                _set_order_status_safely(db, order, OrderStatus.PAID)
                record_payment_event_best_effort(
                    db,
                    order_id=order.id,
                    event="checkout_cancel_resolved_paid",
                    provider="paypal",
                    source="server",
                    message="Cancel flow synced PayPal order and resolved the order as paid.",
                    context={
                        "paypal_order_id": order.paypal_order_id,
                        "paypal_capture_id": _capture_id,
                    },
                    request=request,
                )
                return CheckoutCancelResponse(
                    canceled=False, status=OrderStatus.PAID.value
                )
            if resolved_status == OrderStatus.FAILED:
                _set_order_failed_safely(
                    db,
                    order,
                    diagnostics=build_paypal_failure_diagnostics(paypal_order_payload),
                )
                record_payment_event_best_effort(
                    db,
                    order_id=order.id,
                    event="checkout_cancel_resolved_failed",
                    provider="paypal",
                    source="server",
                    message="Cancel flow synced PayPal order and resolved the order as failed.",
                    context={
                        "paypal_order_id": order.paypal_order_id,
                        "paypal_capture_id": _capture_id,
                    },
                    request=request,
                )
                return CheckoutCancelResponse(
                    canceled=True, status=OrderStatus.FAILED.value
                )

            paypal_order_status = (
                paypal_order_payload.get("status")
                if isinstance(paypal_order_payload, dict)
                else None
            )
            if isinstance(paypal_order_status, str) and paypal_order_status.upper() in {
                "CREATED",
                "SAVED",
                "APPROVED",
                "PAYER_ACTION_REQUIRED",
            }:
                try:
                    paypal_void_order(order.paypal_order_id)
                    paypal_cancel_confirmed = True
                    record_payment_event_best_effort(
                        db,
                        order_id=order.id,
                        event="paypal_order_voided_by_cancel",
                        provider="paypal",
                        source="server",
                        message="Open PayPal order was voided after customer cancel return.",
                        context={
                            "paypal_order_id": order.paypal_order_id,
                            "paypal_status_before": paypal_order_status,
                        },
                        request=request,
                    )
                except PayPalApiError as exc:
                    log_critical_event(
                        domain="payment",
                        event="paypal_order_void_failed",
                        message="Failed to void PayPal order during cancellation.",
                        request=request,
                        context={"order_id": order.id, "user_id": user_id},
                        exc=exc,
                        level=logging.WARNING,
                    )
                    record_payment_event_best_effort(
                        db,
                        order_id=order.id,
                        event="paypal_order_void_failed",
                        provider="paypal",
                        source="server",
                        message="Failed to void PayPal order during cancel flow.",
                        context={
                            "paypal_order_id": order.paypal_order_id,
                            "paypal_status_before": paypal_order_status,
                        },
                        request=request,
                    )

    provider_cancellation_confirmed = all(
        value is True
        for value in (stripe_cancel_confirmed, paypal_cancel_confirmed)
        if value is not None
    )
    if not provider_cancellation_confirmed:
        db.refresh(order)
        record_payment_event_best_effort(
            db,
            order_id=order.id,
            event="checkout_cancel_pending_provider_confirmation",
            provider=provider,
            source="server",
            message="Checkout cancellation was not finalized because the provider state could not be confirmed.",
            stripe_session_id=order.stripe_session_id,
            context={"order_status": order.status.value},
            request=request,
        )
        return CheckoutCancelResponse(canceled=False, status=order.status.value)

    updated = db.execute(
        update(Order)
        .where(Order.id == order.id, Order.status == OrderStatus.PENDING)
        .values(status=OrderStatus.CANCELED)
    )
    db.commit()
    db.refresh(order)
    if not updated.rowcount:
        record_payment_event_best_effort(
            db,
            order_id=order.id,
            event="checkout_cancel_concurrent_status_change",
            provider=provider,
            source="server",
            message="Checkout cancellation did not overwrite a concurrent payment status update.",
            stripe_session_id=order.stripe_session_id,
            context={"order_status": order.status.value},
            request=request,
        )
        return CheckoutCancelResponse(
            canceled=order.status in {OrderStatus.CANCELED, OrderStatus.FAILED},
            status=order.status.value,
        )
    record_payment_event_best_effort(
        db,
        order_id=order.id,
        event="checkout_marked_canceled",
        provider=provider,
        source="server",
        message="Checkout order was marked canceled after cancel return.",
        stripe_session_id=order.stripe_session_id,
        context={"order_status": OrderStatus.CANCELED.value},
        request=request,
    )
    return CheckoutCancelResponse(canceled=True, status=OrderStatus.CANCELED.value)


@router.post("/status", response_model=CheckoutStatusResponse)
async def checkout_status(
    payload: CheckoutStatusRequest,
    request: Request,
    user=Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    user_id = user.id if user else None
    order = db.get(Order, payload.order_id)
    if not order:
        log_critical_event(
            domain="payment",
            event="checkout_status_order_not_found",
            message="Checkout status requested for a missing order.",
            request=request,
            context={"order_id": payload.order_id, "user_id": user_id},
            level=logging.WARNING,
        )
        raise HTTPException(status_code=404, detail="Not found")
    if not _is_order_access_allowed(order, user=user, request=request):
        log_critical_event(
            domain="payment",
            event="checkout_status_unauthorized",
            message="Checkout status denied: invalid user/token for order.",
            request=request,
            context={"order_id": payload.order_id, "user_id": user_id},
            level=logging.WARNING,
        )
        raise HTTPException(status_code=404, detail="Not found")

    provider = _payment_provider_for_order(order)
    status_before = order.status.value
    record_payment_event_best_effort(
        db,
        order_id=order.id,
        event="checkout_status_requested",
        provider=provider,
        source="browser",
        message="Checkout success page requested order payment status.",
        stripe_session_id=order.stripe_session_id,
        context={"order_status_before": status_before},
        request=request,
    )

    stripe_sync_status = None
    paypal_sync_status = None
    if order.status == OrderStatus.PENDING:
        if order.stripe_session_id and settings.stripe_secret_key:
            stripe_sync_status = sync_order_with_stripe(db, order)
        if order.paypal_order_id and paypal_is_configured():
            paypal_sync_status = sync_order_with_paypal(db, order)
        db.refresh(order)

    record_payment_event_best_effort(
        db,
        order_id=order.id,
        event="checkout_status_resolved",
        provider=_payment_provider_for_order(order),
        source="server",
        message="Checkout status request completed.",
        stripe_session_id=order.stripe_session_id,
        context={
            "order_status_before": status_before,
            "order_status_after": order.status.value,
            "stripe_sync_status": (
                stripe_sync_status.value if stripe_sync_status else None
            ),
            "paypal_sync_status": (
                paypal_sync_status.value if paypal_sync_status else None
            ),
        },
        request=request,
    )
    return CheckoutStatusResponse(status=order.status.value)
