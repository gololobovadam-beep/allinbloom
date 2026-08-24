from __future__ import annotations

from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db, get_current_user, require_admin
from app.core.config import settings
from app.core.critical_logging import log_critical_event
from app.models.enums import OrderStatus
from app.models.order import Order
from app.models.payment_event import PaymentEvent
from app.schemas.order import (
    OrderCountOut,
    OrderOut,
    PaymentEventOut,
    OrderSoftDeleteOut,
    OrderToggleOut,
    OrdersByDayOut,
    OrdersByWeekOut,
    StripeAddressOut,
    StripeSessionOut,
    StripeShippingOut,
)
from app.services.payment_diagnostics import resolve_stripe_payment_intent
from app.services.orders import (
    expire_pending_orders,
    get_admin_orders,
    get_admin_orders_by_day,
    get_admin_orders_by_week,
    get_orders_by_email,
    sync_order_with_paypal,
    sync_order_with_stripe,
)
from app.utils.admin_orders import parse_day_key

router = APIRouter(prefix="/api", tags=["orders"])


def _parse_optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _read_provider_attr(obj: object, key: str) -> object:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _read_nested_provider_attr(obj: object, *keys: str) -> object:
    value = obj
    for key in keys:
        value = _read_provider_attr(value, key)
        if value is None:
            return None
    return value


@router.get("/orders/me", response_model=list[OrderOut])
def list_my_orders(user=Depends(get_current_user), db: Session = Depends(get_db)):
    orders = get_orders_by_email(db, user.email)
    return orders


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: str, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    expire_pending_orders(db)
    order = (
        db.execute(select(Order).where(Order.id == order_id).options(joinedload(Order.items)))
        .unique()
        .scalars()
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Not found")
    if order.status == OrderStatus.PENDING:
        sync_order_with_stripe(db, order)
        sync_order_with_paypal(db, order)
    return order


@router.get("/admin/orders", response_model=list[OrderOut])
def list_admin_orders(db: Session = Depends(get_db), _admin=Depends(require_admin)):
    return get_admin_orders(db)


@router.get("/admin/orders/new-count", response_model=OrderCountOut)
def new_orders_count(db: Session = Depends(get_db), _admin=Depends(require_admin)):
    count = db.execute(
        select(func.count())
        .select_from(Order)
        .where(Order.is_read.is_(False), Order.is_deleted.is_(False))
    ).scalar_one()
    return OrderCountOut(count=count)


@router.get("/admin/orders/by-day", response_model=OrdersByDayOut)
def orders_by_day(
    date: str = Query(..., alias="date"),
    scope: str = Query("active"),
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    if not parse_day_key(date):
        raise HTTPException(status_code=400, detail="Invalid date")
    if scope not in {"active", "deleted"}:
        raise HTTPException(status_code=400, detail="Invalid scope")
    orders = get_admin_orders_by_day(db, date, only_deleted=scope == "deleted")
    return OrdersByDayOut(day_key=date, orders=orders)


@router.get("/admin/orders/by-week", response_model=OrdersByWeekOut)
def orders_by_week(
    start_date: str = Query(..., alias="startDate"),
    scope: str = Query("active"),
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    if not parse_day_key(start_date):
        raise HTTPException(status_code=400, detail="Invalid date")
    if scope not in {"active", "deleted"}:
        raise HTTPException(status_code=400, detail="Invalid scope")
    orders = get_admin_orders_by_week(db, start_date, only_deleted=scope == "deleted")
    return OrdersByWeekOut(week_start_key=start_date, orders=orders)


@router.patch("/admin/orders/{order_id}/toggle-read", response_model=OrderToggleOut)
def toggle_read(
    order_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Not found")
    order.is_read = not bool(order.is_read)
    db.commit()
    db.refresh(order)
    return OrderToggleOut(is_read=bool(order.is_read))


@router.patch("/admin/orders/{order_id}/soft-delete", response_model=OrderSoftDeleteOut)
def soft_delete_order(
    order_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Not found")
    if order.is_deleted:
        return OrderSoftDeleteOut(is_deleted=True)

    order.is_deleted = True
    order.deleted_at = datetime.now(timezone.utc)
    order.is_read = True
    db.commit()
    return OrderSoftDeleteOut(is_deleted=True)


@router.patch("/admin/orders/{order_id}/restore", response_model=OrderSoftDeleteOut)
def restore_order(
    order_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Not found")
    if not order.is_deleted:
        return OrderSoftDeleteOut(is_deleted=False)

    order.is_deleted = False
    order.deleted_at = None
    db.commit()
    return OrderSoftDeleteOut(is_deleted=False)


@router.get("/admin/orders/{order_id}/stripe-session", response_model=StripeSessionOut)
def get_order_stripe_session(
    order_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Not found")

    if not settings.stripe_secret_key or not order.stripe_session_id:
        return StripeSessionOut()

    stripe.api_key = settings.stripe_secret_key
    try:
        session = stripe.checkout.Session.retrieve(
            order.stripe_session_id,
            expand=["payment_intent", "payment_intent.latest_charge"],
        )
    except Exception as exc:
        log_critical_event(
            domain="payment",
            event="stripe_session_fetch_failed",
            message="Admin failed to load Stripe session for order.",
            context={"order_id": order_id},
            exc=exc,
        )
        raise HTTPException(status_code=502, detail="Unable to load Stripe session.")

    shipping = getattr(session, "shipping_details", None)
    address = getattr(shipping, "address", None) if shipping else None
    metadata = getattr(session, "metadata", None) or {}
    payment_intent = resolve_stripe_payment_intent(getattr(session, "payment_intent", None))
    last_payment_error = (
        _read_provider_attr(payment_intent, "last_payment_error") if payment_intent else None
    )
    latest_charge = (
        _read_provider_attr(payment_intent, "latest_charge") if payment_intent else None
    )
    charge_outcome = _read_provider_attr(latest_charge, "outcome")
    card_details = _read_nested_provider_attr(
        latest_charge, "payment_method_details", "card"
    )
    card_checks = _read_provider_attr(card_details, "checks")
    return StripeSessionOut(
        payment_status=getattr(session, "payment_status", None),
        status=getattr(session, "status", None),
        created=getattr(session, "created", None),
        expires_at=getattr(session, "expires_at", None),
        payment_intent_id=_read_provider_attr(payment_intent, "id"),
        payment_intent_status=_read_provider_attr(payment_intent, "status"),
        last_payment_error_code=_read_provider_attr(last_payment_error, "code"),
        last_payment_error_decline_code=_read_provider_attr(
            last_payment_error, "decline_code"
        ),
        last_payment_error_message=_read_provider_attr(last_payment_error, "message"),
        latest_charge_id=_read_provider_attr(latest_charge, "id"),
        latest_charge_status=_read_provider_attr(latest_charge, "status"),
        charge_failure_code=_read_provider_attr(latest_charge, "failure_code"),
        charge_failure_message=_read_provider_attr(latest_charge, "failure_message"),
        charge_outcome_type=_read_provider_attr(charge_outcome, "type"),
        charge_outcome_reason=_read_provider_attr(charge_outcome, "reason"),
        charge_outcome_network_status=_read_provider_attr(charge_outcome, "network_status"),
        charge_outcome_seller_message=_read_provider_attr(
            charge_outcome, "seller_message"
        ),
        card_brand=_read_provider_attr(card_details, "brand"),
        card_funding=_read_provider_attr(card_details, "funding"),
        card_country=_read_provider_attr(card_details, "country"),
        card_check_address_postal_code=_read_provider_attr(
            card_checks, "address_postal_code_check"
        ),
        card_check_cvc=_read_provider_attr(card_checks, "cvc_check"),
        shipping=StripeShippingOut(
            name=getattr(shipping, "name", None),
            phone=getattr(shipping, "phone", None),
            address=StripeAddressOut(
                line1=getattr(address, "line1", None),
                line2=getattr(address, "line2", None),
                city=getattr(address, "city", None),
                state=getattr(address, "state", None),
                postal_code=getattr(address, "postal_code", None),
                country=getattr(address, "country", None),
            )
            if address
            else None,
        )
        if shipping
        else None,
        delivery_address=metadata.get("deliveryAddress"),
        delivery_date_time=metadata.get("deliveryDateTime"),
        delivery_miles=metadata.get("deliveryMiles"),
        delivery_fee_cents=_parse_optional_int(metadata.get("deliveryFeeCents")),
        first_order_discount_percent=_parse_optional_int(
            metadata.get("firstOrderDiscountPercent")
        ),
    )


@router.get("/admin/orders/{order_id}/payment-events", response_model=list[PaymentEventOut])
def get_order_payment_events(
    order_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    order_exists = db.execute(select(Order.id).where(Order.id == order_id)).first()
    if not order_exists:
        raise HTTPException(status_code=404, detail="Not found")
    return (
        db.execute(
            select(PaymentEvent)
            .where(PaymentEvent.order_id == order_id)
            .order_by(PaymentEvent.created_at.asc(), PaymentEvent.id.asc())
        )
        .scalars()
        .all()
    )
