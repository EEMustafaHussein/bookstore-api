"""Card payments through Stripe Checkout.

The customer types their card on Stripe's own secure page, so card numbers never
reach this server. Stripe accepts Mastercard, Visa, American Express, Apple Pay and Google Pay.
"""

import hashlib
import hmac
import json
import time

import httpx

from app.config import settings
from app.models import Order

API_BASE = "https://api.stripe.com/v1"
# Stripe requires a checkout page to stay open at least 30 minutes.
SESSION_LIFETIME_SECONDS = 45 * 60
SIGNATURE_TOLERANCE_SECONDS = 300
ZERO_DECIMAL_CURRENCIES = {
    "bif", "clp", "djf", "gnf", "jpy", "kmf", "krw", "mga", "pyg",
    "rwf", "ugx", "vnd", "vuv", "xaf", "xof", "xpf",
}

# Tests replace this with an httpx.MockTransport.
transport: httpx.BaseTransport | None = None


class PaymentError(Exception):
    pass


def _client() -> httpx.Client:
    if not settings.stripe_secret_key:
        raise PaymentError("الدفع بالبطاقة غير مفعّل")
    return httpx.Client(
        base_url=API_BASE,
        headers={"Authorization": f"Bearer {settings.stripe_secret_key}"},
        timeout=10,
        transport=transport,
    )


def amount_in_minor_units(total: int) -> int:
    rate = settings.stripe_exchange_rate if settings.stripe_exchange_rate > 0 else 1
    amount = total / rate
    if settings.stripe_currency.lower() in ZERO_DECIMAL_CURRENCIES:
        return max(round(amount), 1)
    return max(round(amount * 100), 1)


def _send(method: str, path: str, data: dict | None = None) -> dict:
    try:
        with _client() as client:
            response = client.request(method, path, data=data)
    except httpx.HTTPError as exc:
        raise PaymentError("تعذّر الاتصال بخدمة الدفع، حاولي بعد قليل") from exc
    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.status_code >= 400:
        message = body.get("error", {}).get("message") or "رفضت خدمة الدفع الطلب"
        raise PaymentError(message)
    return body


def create_checkout_session(order: Order, customer_email: str, site_name: str) -> dict:
    summary = "، ".join(f"{item.product_name} × {item.quantity}" for item in order.items)
    base = settings.base_url.rstrip("/")
    data = {
        "mode": "payment",
        "success_url": f"{base}/checkout/success?order={order.id}&session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{base}/checkout/cancel?order={order.id}",
        "client_reference_id": str(order.id),
        "customer_email": customer_email,
        "expires_at": str(int(time.time()) + SESSION_LIFETIME_SECONDS),
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": settings.stripe_currency.lower(),
        "line_items[0][price_data][unit_amount]": str(amount_in_minor_units(order.total)),
        "line_items[0][price_data][product_data][name]": f"{site_name} — طلب رقم {order.id}",
        "line_items[0][price_data][product_data][description]": summary[:450] or "طلب",
        "metadata[order_id]": str(order.id),
        "payment_intent_data[metadata][order_id]": str(order.id),
    }
    return _send("POST", "/checkout/sessions", data)


def retrieve_checkout_session(session_id: str) -> dict:
    if not session_id.startswith("cs_") or not session_id.replace("_", "").isalnum():
        raise PaymentError("رقم عملية الدفع غير صحيح")
    return _send("GET", f"/checkout/sessions/{session_id}")


def session_is_paid(checkout_session: dict, order: Order) -> bool:
    return (
        checkout_session.get("payment_status") == "paid"
        and str(checkout_session.get("client_reference_id")) == str(order.id)
    )


def parse_webhook(payload: bytes, signature_header: str | None) -> dict:
    """Checks the Stripe-Signature header and returns the event, or raises PaymentError."""
    secret = settings.stripe_webhook_secret
    if not secret or not signature_header:
        raise PaymentError("missing signature")

    timestamp = None
    signatures = []
    for part in signature_header.split(","):
        key, _, value = part.strip().partition("=")
        if key == "t":
            timestamp = value
        elif key == "v1":
            signatures.append(value)
    if timestamp is None or not timestamp.isdigit() or not signatures:
        raise PaymentError("bad signature header")
    if abs(time.time() - int(timestamp)) > SIGNATURE_TOLERANCE_SECONDS:
        raise PaymentError("signature too old")

    signed = timestamp.encode() + b"." + payload
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, given) for given in signatures):
        raise PaymentError("signature mismatch")
    try:
        return json.loads(payload)
    except ValueError as exc:
        raise PaymentError("bad payload") from exc
