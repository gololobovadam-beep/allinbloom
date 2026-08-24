from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String, func
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.enums import OrderStatus
from app.utils.ids import generate_cuid


class Order(Base):
    __tablename__ = "Order"

    id = Column(String, primary_key=True, default=generate_cuid)
    email = Column(String, nullable=True, index=True)
    phone = Column(String, nullable=True)
    stripe_session_id = Column("stripeSessionId", String, unique=True, nullable=True)
    stripe_payment_intent_id = Column("stripePaymentIntentId", String, unique=True, nullable=True)
    stripe_charge_id = Column("stripeChargeId", String, unique=True, nullable=True)
    paypal_order_id = Column("paypalOrderId", String, unique=True, nullable=True)
    paypal_capture_id = Column("paypalCaptureId", String, unique=True, nullable=True)
    payment_provider = Column("paymentProvider", String, nullable=True)
    checkout_idempotency_key = Column(
        "checkoutIdempotencyKey", String, unique=True, nullable=True
    )
    checkout_request_fingerprint = Column("checkoutRequestFingerprint", String, nullable=True)
    checkout_redirect_url = Column("checkoutRedirectUrl", String, nullable=True)
    total_cents = Column("totalCents", Integer, nullable=False)
    refunded_cents = Column(
        "refundedCents", Integer, nullable=False, default=0, server_default="0"
    )
    currency = Column(String, default="USD", nullable=False)
    delivery_address = Column("deliveryAddress", String, nullable=True)
    delivery_address_line1 = Column("deliveryAddressLine1", String, nullable=True)
    delivery_address_line2 = Column("deliveryAddressLine2", String, nullable=True)
    delivery_city = Column("deliveryCity", String, nullable=True)
    delivery_state = Column("deliveryState", String, nullable=True)
    delivery_postal_code = Column("deliveryPostalCode", String, nullable=True)
    delivery_country = Column("deliveryCountry", String, nullable=True)
    delivery_floor = Column("deliveryFloor", String, nullable=True)
    delivery_date_time = Column("deliveryDateTime", String, nullable=True)
    order_comment = Column("orderComment", String, nullable=True)
    delivery_miles = Column("deliveryMiles", String, nullable=True)
    delivery_fee_cents = Column("deliveryFeeCents", Integer, nullable=True)
    first_order_discount_percent = Column("firstOrderDiscountPercent", Integer, nullable=True)
    payment_failure_stage = Column("paymentFailureStage", String, nullable=True)
    payment_failure_code = Column("paymentFailureCode", String, nullable=True)
    payment_failure_message = Column("paymentFailureMessage", String, nullable=True)
    payment_failure_details = Column("paymentFailureDetails", String, nullable=True)
    payment_failed_at = Column("paymentFailedAt", DateTime(timezone=True), nullable=True)
    status = Column(Enum(OrderStatus, name="OrderStatus"), default=OrderStatus.PENDING, nullable=False)
    is_read = Column("isRead", Boolean, default=False, nullable=False)
    is_deleted = Column("isDeleted", Boolean, default=False, nullable=False)
    deleted_at = Column("deletedAt", DateTime(timezone=True), nullable=True)
    created_at = Column(
        "createdAt", DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    items = relationship("OrderItem", back_populates="order", cascade="all, delete")
