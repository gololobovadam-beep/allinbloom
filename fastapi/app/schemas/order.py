from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from app.models.enums import OrderStatus
from app.schemas.base import SchemaBase


class OrderItemOut(SchemaBase):
    id: str
    order_id: str
    bouquet_id: Optional[str] = None
    name: str
    price_cents: int
    quantity: int
    image: str
    details: Optional[str] = None


class OrderOut(SchemaBase):
    id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    stripe_session_id: Optional[str] = None
    paypal_order_id: Optional[str] = None
    paypal_capture_id: Optional[str] = None
    total_cents: int
    currency: str
    status: OrderStatus
    is_read: bool
    delivery_address: Optional[str] = None
    delivery_address_line1: Optional[str] = None
    delivery_address_line2: Optional[str] = None
    delivery_city: Optional[str] = None
    delivery_state: Optional[str] = None
    delivery_postal_code: Optional[str] = None
    delivery_country: Optional[str] = None
    delivery_floor: Optional[str] = None
    delivery_date_time: Optional[str] = None
    order_comment: Optional[str] = None
    delivery_miles: Optional[str] = None
    delivery_fee_cents: Optional[int] = None
    first_order_discount_percent: Optional[int] = None
    payment_failure_stage: Optional[str] = None
    payment_failure_code: Optional[str] = None
    payment_failure_message: Optional[str] = None
    payment_failure_details: Optional[str] = None
    payment_failed_at: Optional[datetime] = None
    created_at: datetime
    items: list[OrderItemOut]


class OrderToggleOut(SchemaBase):
    is_read: bool


class OrderSoftDeleteOut(SchemaBase):
    is_deleted: bool


class OrderCountOut(SchemaBase):
    count: int


class OrdersByDayOut(SchemaBase):
    day_key: str
    orders: list[OrderOut]


class OrdersByWeekOut(SchemaBase):
    week_start_key: str
    orders: list[OrderOut]


class OrdersPageOut(SchemaBase):
    orders: list[OrderOut]
    has_more: bool
    next_offset: Optional[int] = None


class StripeAddressOut(SchemaBase):
    line1: Optional[str] = None
    line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None


class StripeShippingOut(SchemaBase):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[StripeAddressOut] = None


class StripeSessionOut(SchemaBase):
    payment_status: Optional[str] = None
    status: Optional[str] = None
    created: Optional[int] = None
    expires_at: Optional[int] = None
    payment_intent_id: Optional[str] = None
    payment_intent_status: Optional[str] = None
    last_payment_error_code: Optional[str] = None
    last_payment_error_decline_code: Optional[str] = None
    last_payment_error_message: Optional[str] = None
    latest_charge_id: Optional[str] = None
    latest_charge_status: Optional[str] = None
    charge_failure_code: Optional[str] = None
    charge_failure_message: Optional[str] = None
    charge_outcome_type: Optional[str] = None
    charge_outcome_reason: Optional[str] = None
    charge_outcome_network_status: Optional[str] = None
    charge_outcome_seller_message: Optional[str] = None
    card_brand: Optional[str] = None
    card_funding: Optional[str] = None
    card_country: Optional[str] = None
    card_check_address_postal_code: Optional[str] = None
    card_check_cvc: Optional[str] = None
    shipping: Optional[StripeShippingOut] = None
    delivery_address: Optional[str] = None
    delivery_date_time: Optional[str] = None
    delivery_miles: Optional[str] = None
    delivery_fee_cents: Optional[int] = None
    first_order_discount_percent: Optional[int] = None


class PaymentEventOut(SchemaBase):
    id: str
    order_id: str
    provider: str
    source: str
    event: str
    message: Optional[str] = None
    stripe_session_id: Optional[str] = None
    stripe_event_id: Optional[str] = None
    payment_intent_id: Optional[str] = None
    context: Optional[dict[str, Any]] = None
    created_at: datetime
