import hashlib
import hmac
import json
import time

import httpx
import pytest
from sqlmodel import select

from app.config import settings
from app.enums import OrderStatus, PaymentStatus
from app.models import Order, Product
from app.payments import stripe
from tests.conftest import login, make_product, make_user, post
from tests.test_cart_checkout import ADDRESS, add

WEBHOOK_SECRET = "whsec_test_secret"


def place_card_order(client, db, stock=1):
    make_user(db, email="sara@example.com")
    product = make_product(db, stock=stock, price=131000)
    login(client, "sara@example.com")
    add(client, product)
    response = post(client, "/checkout", {**ADDRESS, "payment_method": "card"})
    assert response.status_code == 303
    order = db.exec(select(Order)).one()
    assert response.headers["location"] == f"/checkout/pay/{order.id}"
    return order, product


def signed(payload: dict) -> tuple[bytes, str]:
    body = json.dumps(payload).encode()
    timestamp = str(int(time.time()))
    signature = hmac.new(WEBHOOK_SECRET.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return body, f"t={timestamp},v1={signature}"


def test_card_option_hidden_when_not_configured(client, db):
    make_user(db, email="sara@example.com")
    product = make_product(db)
    login(client, "sara@example.com")
    add(client, product)
    assert 'value="card"' not in client.get("/checkout").text
    response = post(client, "/checkout", {**ADDRESS, "payment_method": "card"})
    assert response.status_code == 400


def test_demo_card_payment(client, db, monkeypatch):
    monkeypatch.setattr(settings, "payment_demo_mode", True)
    order, _ = place_card_order(client, db)
    page = client.get(f"/checkout/pay/{order.id}")
    assert page.status_code == 200 and "صفحة دفع تجريبية" in page.text

    post(client, f"/checkout/demo/{order.id}", {"action": "cancel"})
    db.refresh(order)
    assert order.status == OrderStatus.awaiting_payment

    response = post(client, f"/checkout/demo/{order.id}", {"action": "pay"})
    assert response.headers["location"] == f"/account/orders/{order.id}?placed=1"
    db.refresh(order)
    assert order.payment_status == PaymentStatus.paid and order.status == OrderStatus.new
    assert order.payment_provider == "demo"


def test_demo_payment_is_off_by_default(client, db, monkeypatch):
    monkeypatch.setattr(settings, "payment_demo_mode", True)
    order, _ = place_card_order(client, db)
    monkeypatch.setattr(settings, "payment_demo_mode", False)
    assert post(client, f"/checkout/demo/{order.id}", {"action": "pay"}).status_code == 404
    db.refresh(order)
    assert order.payment_status == PaymentStatus.unpaid


@pytest.fixture
def stripe_api(monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_123")
    monkeypatch.setattr(settings, "stripe_webhook_secret", WEBHOOK_SECRET)
    monkeypatch.setattr(settings, "stripe_currency", "usd")
    monkeypatch.setattr(settings, "stripe_exchange_rate", 1310.0)
    state = {"requests": [], "paid": False}

    def handler(request: httpx.Request) -> httpx.Response:
        state["requests"].append(request)
        assert request.headers["authorization"] == "Bearer sk_test_123"
        if request.method == "POST" and request.url.path == "/v1/checkout/sessions":
            form = dict(httpx.QueryParams(request.content.decode()))
            state["created"] = form
            return httpx.Response(
                200,
                json={"id": "cs_test_abc", "url": "https://checkout.stripe.com/c/pay/cs_test_abc"},
            )
        if request.method == "GET" and request.url.path == "/v1/checkout/sessions/cs_test_abc":
            order_id = state["created"]["client_reference_id"]
            return httpx.Response(
                200,
                json={
                    "id": "cs_test_abc",
                    "status": "complete" if state["paid"] else "open",
                    "payment_status": "paid" if state["paid"] else "unpaid",
                    "client_reference_id": order_id,
                },
            )
        return httpx.Response(404, json={"error": {"message": "not found"}})

    monkeypatch.setattr(stripe, "transport", httpx.MockTransport(handler))
    return state


def test_stripe_checkout_success_flow(client, db, stripe_api):
    order, _ = place_card_order(client, db)
    response = client.get(f"/checkout/pay/{order.id}", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("https://checkout.stripe.com/")
    created = stripe_api["created"]
    # 131,000 dinars (free shipping) / 1310 per dollar = 100 dollars, sent in cents.
    assert created["line_items[0][price_data][unit_amount]"] == "10000"
    assert created["line_items[0][price_data][currency]"] == "usd"
    assert created["success_url"].endswith("session_id={CHECKOUT_SESSION_ID}")
    db.refresh(order)
    assert order.payment_reference == "cs_test_abc"

    # Not paid yet: the order stays waiting.
    client.get(f"/checkout/success?order={order.id}&session_id=cs_test_abc")
    db.refresh(order)
    assert order.payment_status == PaymentStatus.unpaid

    stripe_api["paid"] = True
    response = client.get(f"/checkout/success?order={order.id}&session_id=cs_test_abc", follow_redirects=False)
    assert response.headers["location"] == f"/account/orders/{order.id}?placed=1"
    db.refresh(order)
    assert order.payment_status == PaymentStatus.paid and order.status == OrderStatus.new


def test_stripe_webhook_marks_paid_and_checks_signature(client, db, stripe_api):
    order, _ = place_card_order(client, db)
    client.get(f"/checkout/pay/{order.id}", follow_redirects=False)
    event = {
        "type": "checkout.session.completed",
        "data": {"object": {"id": "cs_test_abc", "payment_status": "paid", "client_reference_id": str(order.id)}},
    }
    body, header = signed(event)

    forged = client.post("/checkout/stripe/webhook", content=body, headers={"stripe-signature": "t=1,v1=bad"})
    assert forged.status_code == 400
    db.refresh(order)
    assert order.payment_status == PaymentStatus.unpaid

    ok = client.post("/checkout/stripe/webhook", content=body, headers={"stripe-signature": header})
    assert ok.status_code == 200
    db.refresh(order)
    assert order.payment_status == PaymentStatus.paid


def test_stripe_expired_session_restores_stock(client, db, stripe_api):
    order, product = place_card_order(client, db)
    client.get(f"/checkout/pay/{order.id}", follow_redirects=False)
    db.refresh(product)
    assert product.stock == 0
    body, header = signed(
        {"type": "checkout.session.expired", "data": {"object": {"id": "cs_test_abc", "client_reference_id": str(order.id)}}}
    )
    assert client.post("/checkout/stripe/webhook", content=body, headers={"stripe-signature": header}).status_code == 200
    db.refresh(order)
    db.refresh(product)
    assert order.status == OrderStatus.cancelled and product.stock == 1


def test_stripe_errors_are_shown_not_crashed(client, db, monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_123")

    def failing(request):
        return httpx.Response(400, json={"error": {"message": "Amount too small"}})

    monkeypatch.setattr(stripe, "transport", httpx.MockTransport(failing))
    order, _ = place_card_order(client, db)
    response = client.get(f"/checkout/pay/{order.id}")
    assert response.status_code == 200
    assert "Amount too small" in response.text
    assert db.get(Product, order.items[0].product_id) is not None
