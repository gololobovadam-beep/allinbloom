from __future__ import annotations

from datetime import date, datetime
import json
import logging
from typing import Iterable

import httpx

from app.core.config import settings


RESEND_ENDPOINT = "https://api.resend.com/emails"
logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    pass


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _format_money(value: int) -> str:
    return f"${value / 100:,.2f}"


def _resolve_reply_to(candidate: str | None = None) -> str:
    return candidate or settings.email_reply_to or settings.admin_email


def _extract_resend_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        message = payload.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()

    text = (response.text or "").strip()
    if text:
        return text
    return f"HTTP {response.status_code}"


def _format_fee(value: str | int | None) -> str:
    if value is None:
        return "-"
    try:
        cents = int(value)
    except (TypeError, ValueError):
        return str(value)
    return _format_money(cents)


def _format_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return value
    return parsed.strftime("%b ") + str(parsed.day) + parsed.strftime(", %Y")


def _format_time(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%H:%M")
    except ValueError:
        return value
    hour = parsed.hour % 12 or 12
    suffix = "AM" if parsed.hour < 12 else "PM"
    return f"{hour}:{parsed.minute:02d} {suffix}"


def _format_delivery_date_time(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return "-"

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw

    if not isinstance(parsed, dict):
        return raw

    date_value = parsed.get("date")
    time_window = parsed.get("timeWindow")
    ideal_time = parsed.get("idealTime")
    if not isinstance(date_value, str) or not isinstance(time_window, str):
        return raw

    parts = [f"Date: {_format_date(date_value)}", f"Window: {time_window}"]
    if isinstance(ideal_time, str) and ideal_time.strip():
        parts.append(f"Ideal delivery time: {_format_time(ideal_time.strip())}")
    return "; ".join(parts)


def _format_item_details_text(item: dict) -> str:
    details = str(item.get("details") or "").strip()
    if not details:
        return ""
    return f" | {details}"


def _format_item_details_html(item: dict) -> str:
    details = str(item.get("details") or "").strip()
    if not details:
        return ""
    return f" <span style=\"color:#6b7280\">({_escape(details)})</span>"


def _format_delivery_address(params: dict) -> str:
    direct = params.get("delivery_address")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    line1 = str(params.get("delivery_address_line1") or "").strip()
    if not line1:
        return "-"
    line2 = str(params.get("delivery_address_line2") or "").strip()
    floor = str(params.get("delivery_floor") or "").strip()
    city = str(params.get("delivery_city") or "").strip()
    state = str(params.get("delivery_state") or "").strip()
    postal_code = str(params.get("delivery_postal_code") or "").strip()
    country = str(params.get("delivery_country") or "").strip()

    extras = []
    if line2:
        extras.append(line2)
    if floor:
        if floor.lower().startswith("floor"):
            extras.append(floor)
        else:
            extras.append(f"Floor {floor}")
    if extras:
        line1 = f"{line1}, {', '.join(extras)}"

    state_zip = " ".join(part for part in [state, postal_code] if part)
    city_state_zip = ", ".join(part for part in [city, state_zip] if part)
    parts = [line1, city_state_zip, country]
    formatted = ", ".join(part for part in parts if part)
    return formatted or "-"


async def send_email(to: Iterable[str], subject: str, text: str, html: str, reply_to: str) -> None:
    if not settings.resend_api_key:
        # A caller that records delivery success must never interpret a
        # missing provider credential as a sent message.  In particular, the
        # payment outbox will retain and retry this work instead of marking a
        # paid order's confirmation as delivered forever.
        raise EmailDeliveryError("RESEND_API_KEY is not configured.")
    payload = {
        "from": settings.email_from,
        "to": list(to),
        "subject": subject,
        "text": text,
        "html": html,
        "reply_to": reply_to,
    }
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.post(
            RESEND_ENDPOINT,
            json=payload,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        )
    if response.status_code >= 400:
        raise EmailDeliveryError(_extract_resend_error(response))


async def send_otp_email(email: str, code: str) -> None:
    subject = "Your All in Bloom Floral Studio verification code"
    text = f"Your one-time code is {code}. It expires in 10 minutes."
    html = f"<p>Your one-time code is <strong>{_escape(code)}</strong>. It expires in 10 minutes.</p>"
    is_dev = settings.is_development()

    if not settings.resend_api_key:
        if is_dev:
            logger.warning("OTP fallback (RESEND_API_KEY is empty): email=%s code=%s", email, code)
            return
        raise EmailDeliveryError("RESEND_API_KEY is not configured.")

    try:
        await send_email([email], subject, text, html, _resolve_reply_to())
    except Exception as exc:
        if is_dev:
            logger.warning("OTP fallback (email provider failed): email=%s code=%s error=%s", email, code, exc)
            return
        raise EmailDeliveryError(str(exc)) from exc


async def send_admin_order_email(params: dict) -> None:
    if not settings.admin_email:
        return
    safe_order = _escape(params["order_id"])
    safe_email = _escape(params.get("email") or "-")
    safe_phone = _escape(params.get("phone") or "-")
    safe_address = _escape(_format_delivery_address(params))
    safe_miles = _escape(params.get("delivery_miles") or "-")
    safe_fee = _escape(_format_fee(params.get("delivery_fee")))
    safe_discount = _escape(params.get("first_order_discount") or "0")
    delivery_date_time = _format_delivery_date_time(params.get("delivery_date_time"))
    safe_delivery_date_time = _escape(delivery_date_time)
    safe_comment = _escape(params.get("order_comment") or "")
    total = _escape(_format_money(params["total_cents"]))

    items = params.get("items") or []
    items_html = "".join(
        f"<li>{item['quantity']} x {_escape(item['name'])} - "
        f"{_escape(_format_money(item['price_cents']))}"
        f"{_format_item_details_html(item)}</li>"
        for item in items
    )
    items_text = "\n".join(
        f"{item['quantity']} x {item['name']} - {_format_money(item['price_cents'])}"
        f"{_format_item_details_text(item)}"
        for item in items
    )

    subject = "New paid order"
    text = "\n".join(
        [
            "Order paid",
            f"Order: {params['order_id']}",
            f"Customer email: {params.get('email') or '-'}",
            f"Phone: {params.get('phone') or '-'}",
            f"Total: {_format_money(params['total_cents'])}",
            f"Delivery address: {_format_delivery_address(params)}",
            f"Delivery date/time: {delivery_date_time}",
            f"Delivery miles: {params.get('delivery_miles') or '-'}",
            f"Delivery fee: {_format_fee(params.get('delivery_fee'))}",
            f"First order discount %: {params.get('first_order_discount') or '0'}",
            f"Order comment: {params.get('order_comment') or '-'}",
            "Items:",
            items_text or "-",
        ]
    )
    html = f"""
      <h2>Order paid</h2>
      <p><strong>Order:</strong> {safe_order}</p>
      <p><strong>Customer email:</strong> {safe_email}</p>
      <p><strong>Phone:</strong> {safe_phone}</p>
      <p><strong>Total:</strong> {total}</p>
      <p><strong>Delivery address:</strong> {safe_address}</p>
      <p><strong>Delivery date/time:</strong> {safe_delivery_date_time or "-"}</p>
      <p><strong>Delivery miles:</strong> {safe_miles}</p>
      <p><strong>Delivery fee:</strong> {safe_fee}</p>
      <p><strong>First order discount %:</strong> {safe_discount}</p>
      <p><strong>Order comment:</strong> {safe_comment or "-"}</p>
      <h3>Items</h3>
      <ul>{items_html}</ul>
    """
    await send_email(
        [settings.admin_email],
        subject,
        text,
        html,
        _resolve_reply_to(params.get("email")),
    )


async def send_customer_order_email(params: dict) -> None:
    if not params.get("email"):
        return
    safe_order = _escape(params["order_id"])
    safe_email = _escape(params.get("email") or "-")
    safe_phone = _escape(params.get("phone") or "-")
    safe_address = _escape(_format_delivery_address(params))
    safe_miles = _escape(params.get("delivery_miles") or "-")
    safe_fee = _escape(_format_fee(params.get("delivery_fee")))
    safe_discount = _escape(params.get("first_order_discount") or "0")
    delivery_date_time = _format_delivery_date_time(params.get("delivery_date_time"))
    safe_delivery_date_time = _escape(delivery_date_time)
    safe_comment = _escape(params.get("order_comment") or "")
    total = _escape(_format_money(params["total_cents"]))

    items = params.get("items") or []
    items_html = "".join(
        f"<li>{item['quantity']} x {_escape(item['name'])} - "
        f"{_escape(_format_money(item['price_cents']))}"
        f"{_format_item_details_html(item)}</li>"
        for item in items
    )
    items_text = "\n".join(
        f"{item['quantity']} x {item['name']} - {_format_money(item['price_cents'])}"
        f"{_format_item_details_text(item)}"
        for item in items
    )

    subject = "Your order is confirmed"
    text = "\n".join(
        [
            "Thank you for your order!",
            f"Order: {params['order_id']}",
            f"Email: {params.get('email') or '-'}",
            f"Phone: {params.get('phone') or '-'}",
            f"Total: {_format_money(params['total_cents'])}",
            f"Delivery address: {_format_delivery_address(params)}",
            f"Delivery date/time: {delivery_date_time}",
            f"Delivery miles: {params.get('delivery_miles') or '-'}",
            f"Delivery fee: {_format_fee(params.get('delivery_fee'))}",
            f"First order discount %: {params.get('first_order_discount') or '0'}",
            f"Order comment: {params.get('order_comment') or '-'}",
            "Items:",
            items_text or "-",
        ]
    )
    html = f"""
      <h2>Thank you for your order!</h2>
      <p><strong>Order:</strong> {safe_order}</p>
      <p><strong>Email:</strong> {safe_email}</p>
      <p><strong>Phone:</strong> {safe_phone}</p>
      <p><strong>Total:</strong> {total}</p>
      <p><strong>Delivery address:</strong> {safe_address}</p>
      <p><strong>Delivery date/time:</strong> {safe_delivery_date_time or "-"}</p>
      <p><strong>Delivery miles:</strong> {safe_miles}</p>
      <p><strong>Delivery fee:</strong> {safe_fee}</p>
      <p><strong>First order discount %:</strong> {safe_discount}</p>
      <p><strong>Order comment:</strong> {safe_comment or "-"}</p>
      <h3>Items</h3>
      <ul>{items_html}</ul>
    """
    await send_email(
        [params["email"]],
        subject,
        text,
        html,
        _resolve_reply_to(),
    )


async def send_contact_email(name: str, email: str, message: str) -> None:
    if not settings.admin_email:
        return
    safe_name = _escape(name)
    safe_email = _escape(email)
    safe_message = _escape(message).replace("\n", "<br>")
    subject = f"New contact form message from {safe_name}"
    text = "\n".join(
        ["New Contact Form Submission", f"Name: {name}", f"Email: {email}", "", message]
    )
    html = f"""
      <h2>New Contact Form Submission</h2>
      <p><strong>Name:</strong> {safe_name}</p>
      <p><strong>Email:</strong> {safe_email}</p>
      <p><strong>Message:</strong></p>
      <p>{safe_message}</p>
    """
    await send_email(
        [settings.admin_email],
        subject,
        text,
        html,
        _resolve_reply_to(email),
    )
