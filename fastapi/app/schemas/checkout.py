from __future__ import annotations

from typing import Any, Optional

from pydantic import Field, field_validator

from app.schemas.base import SchemaBase


MAX_CHECKOUT_ITEMS = 25


class CheckoutItemIn(SchemaBase):
    id: str = Field(min_length=1, max_length=128)
    quantity: int = Field(ge=1, le=1001)
    name: Optional[str] = Field(default=None, max_length=200)
    price_cents: Optional[int] = Field(default=None, ge=0, le=100_000_000)
    image: Optional[str] = Field(default=None, max_length=2048)
    is_custom: Optional[bool] = None
    details: Optional[str] = Field(default=None, max_length=500)

    @field_validator("id", "name", "image", "details", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return str(value).strip() if value is not None else None


class CheckoutRequest(SchemaBase):
    items: list[CheckoutItemIn] = Field(min_length=1, max_length=MAX_CHECKOUT_ITEMS)
    address: Optional[str] = Field(default=None, max_length=500)
    address_line1: Optional[str] = Field(default=None, max_length=200)
    address_line2: Optional[str] = Field(default=None, max_length=200)
    city: Optional[str] = Field(default=None, max_length=120)
    state: Optional[str] = Field(default=None, max_length=80)
    postal_code: Optional[str] = Field(default=None, max_length=24)
    country: Optional[str] = Field(default=None, max_length=80)
    floor: Optional[str] = Field(default=None, max_length=80)
    delivery_date_time: Optional[str] = Field(default=None, max_length=160)
    order_comment: Optional[str] = Field(default=None, max_length=500)
    phone: Optional[str] = Field(default=None, max_length=40)
    email: Optional[str] = Field(default=None, max_length=320)
    payment_method: Optional[str] = Field(default=None, max_length=32)


class CheckoutResponse(SchemaBase):
    url: str
    order_id: Optional[str] = None
    provider: Optional[str] = None


class CheckoutCancelRequest(SchemaBase):
    order_id: Optional[str] = Field(default=None, max_length=128)
    paypal_order_id: Optional[str] = Field(default=None, max_length=128)


class CheckoutCancelResponse(SchemaBase):
    canceled: bool
    status: str


class CheckoutStatusRequest(SchemaBase):
    order_id: str = Field(min_length=1, max_length=128)


class CheckoutStatusResponse(SchemaBase):
    status: str


class CheckoutEventRequest(SchemaBase):
    order_id: str = Field(min_length=1, max_length=128)
    event: str = Field(min_length=1, max_length=80)
    provider: Optional[str] = Field(default=None, max_length=32)
    context: Optional[dict[str, Any]] = Field(default=None, max_length=20)


class CheckoutEventResponse(SchemaBase):
    received: bool
