from __future__ import annotations

from app.schemas.base import SchemaBase
from pydantic import Field


class PayPalCaptureRequest(SchemaBase):
    order_id: str = Field(min_length=1, max_length=128)
    checkout_order_id: str | None = Field(default=None, max_length=128)


class PayPalCaptureResponse(SchemaBase):
    status: str
