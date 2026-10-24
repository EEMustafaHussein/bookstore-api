from datetime import timedelta

from sqlmodel import select

from app.enums import OrderStatus, PaymentMethod, PaymentStatus, Role
from app.models import CartItem, Order, Product
from tests.conftest import login, make_product, make_user, post

JSON = {"Accept": "application/json"}
ADDRESS = {
    "full_name": "سارة أحمد",
    "phone": "٠٧٧٠١٢٣٤٥٦٧",
    "governorate": "بغداد",
    "city": "الكرادة",
    "address": "قرب ساحة الحرية، زقاق 12",
    "notes": "",
    "payment_method": "cod",
}


def add(client, product, **data):
    payload = {"product_id": str(product.id), "quantity": "1", **data}
    return post(client, "/cart/add", payload, headers=JSON)


def test_guest_cart_add_update_remove(client, db):
    dress = make_product(db, stock=3, sizes="S, M", colors="أسود")
    bag = make_product(db, name="حقيبة", stock=1)

    missing = add(client, dress)
    assert missing.status_code == 400 and "المقاس" in missing.json()["message"]
    ok = add(client, dress, size="M", color="أسود", quantity="2")
    assert ok.status_code == 200 and ok.json()["cart"]["count"] == 2
    too_many = add(client, dress, size="S", color="أسود", quantity="2")
    assert too_many.status_code == 400 and "3" in too_many.json()["message"]
    assert add(client, bag).json()["cart"]["count"] == 3
    assert add(client, bag).status_code == 400

    cart = client.get("/api/cart").json()
    assert cart["subtotal_text"] == "75,000 د.ع"
    line = next(item for item in cart["items"] if item["product_id"] == dress.id)
    assert line["max"] == 3

    updated = post(client, f"/cart/items/{line['id']}", {"quantity": "1"}, headers=JSON)
    assert updated.json()["cart"]["count"] == 2
    removed = post(client, f"/cart/items/{line['id']}/remove", headers=JSON)
    assert removed.json()["cart"]["count"] == 1
    assert "حقيبة" in client.get("/cart").text


def test_cart_without_javascript_redirects_back(client, db):
    product = make_product(db)
    response = post(client, "/cart/add", {"product_id": str(product.id)})
    assert response.status_code == 303 and response.headers["location"] == f"/product/{product.id}"
    assert "فستان وردي" in client.get("/cart").text


def test_other_visitors_cannot_touch_my_cart(client, db):
    product = make_product(db)
    add(client, product)
    item = db.exec(select(CartItem)).one()
    client.cookies.clear()
    response = post(client, f"/cart/items/{item.id}/remove", headers=JSON)
    assert response.status_code == 400
    db.refresh(item)
    assert item.quantity == 1


def test_guest_cart_moves_into_account_on_login(client, db):
    make_user(db, email="sara@example.com")
    product = make_product(db)
    add(client, product)
    login(client, "sara@example.com")
    assert client.get("/api/cart").json()["count"] == 1
    item = db.exec(select(CartItem)).one()
    assert item.user_id is not None and item.cart_token is None


def test_checkout_requires_login_and_items(client, db):
    response = client.get("/checkout", follow_redirects=False)
    assert response.headers["location"] == "/login?next=%2Fcheckout"
    make_user(db, email="sara@example.com")
    login(client, "sara@example.com")
    assert client.get("/checkout", follow_redirects=False).headers["location"] == "/cart"


def test_cash_on_delivery_checkout(client, db):
    make_user(db, email="sara@example.com")
    product = make_product(db, stock=2, price=40000)
    login(client, "sara@example.com")
    add(client, product, quantity="2")

    bad = post(client, "/checkout", {**ADDRESS, "phone": "12345", "governorate": "باريس"})
    assert bad.status_code == 400 and "رقم الهاتف غير صحيح" in bad.text and "اختاري المحافظة" in bad.text

    response = post(client, "/checkout", ADDRESS)
    assert response.status_code == 303
    order = db.exec(select(Order)).one()
    assert response.headers["location"] == f"/account/orders/{order.id}?placed=1"
    assert order.status == OrderStatus.new and order.payment_method == PaymentMethod.cod
    assert order.phone == "07701234567"
    # 80,000 is under the 100,000 free-shipping threshold, so the 5,000 fee applies.
    assert (order.subtotal, order.shipping_fee, order.total) == (80000, 5000, 85000)
    db.refresh(product)
    assert product.stock == 0
    assert db.exec(select(CartItem)).first() is None
    page = client.get(f"/account/orders/{order.id}?placed=1")
    assert "تم استلام طلبكِ" in page.text

    post(client, f"/account/orders/{order.id}/cancel")
    db.refresh(order)
    db.refresh(product)
    assert order.status == OrderStatus.cancelled and product.stock == 2


def test_free_shipping_threshold(client, db):
    make_user(db, email="sara@example.com")
    product = make_product(db, stock=5, price=60000)
    login(client, "sara@example.com")
    add(client, product, quantity="2")
    post(client, "/checkout", ADDRESS)
    order = db.exec(select(Order)).one()
    assert order.shipping_fee == 0 and order.total == 120000


def test_last_piece_cannot_be_sold_twice(client, db):
    make_user(db, email="a@example.com")
    make_user(db, email="b@example.com")
    piece = make_product(db, name="جاكيت بالة", stock=1)

    login(client, "a@example.com")
    add(client, piece)
    post(client, "/logout")
    login(client, "b@example.com")
    add(client, piece)
    assert post(client, "/checkout", ADDRESS).status_code == 303
    post(client, "/logout")

    login(client, "a@example.com")
    response = post(client, "/checkout", ADDRESS)
    # The cart notices the piece is gone before an order is made.
    assert response.status_code in (303, 400)
    assert len(db.exec(select(Order)).all()) == 1
    db.refresh(piece)
    assert piece.stock == 0


def test_orders_are_private(client, db):
    make_user(db, email="a@example.com")
    make_user(db, email="b@example.com")
    product = make_product(db)
    login(client, "a@example.com")
    add(client, product)
    post(client, "/checkout", ADDRESS)
    order = db.exec(select(Order)).one()
    post(client, "/logout")
    login(client, "b@example.com")
    assert client.get(f"/account/orders/{order.id}").status_code == 404
    assert post(client, f"/account/orders/{order.id}/cancel").status_code == 404


def test_admin_updates_order_status(client, db):
    make_user(db, email="sara@example.com")
    make_user(db, email="admin@example.com", role=Role.admin)
    product = make_product(db, stock=3)
    login(client, "sara@example.com")
    add(client, product, quantity="2")
    post(client, "/checkout", ADDRESS)
    order = db.exec(select(Order)).one()
    post(client, "/logout")

    login(client, "admin@example.com")
    assert "سارة أحمد" in client.get("/admin/orders").text
    assert client.get(f"/admin/orders/{order.id}").status_code == 200
    post(client, f"/admin/orders/{order.id}/status", {"status": "shipped"})
    db.refresh(order)
    assert order.status == OrderStatus.shipped and order.payment_status == PaymentStatus.unpaid
    post(client, f"/admin/orders/{order.id}/status", {"status": "delivered"})
    db.refresh(order)
    assert order.payment_status == PaymentStatus.paid

    post(client, f"/admin/orders/{order.id}/status", {"status": "cancelled"})
    db.refresh(order)
    db.refresh(product)
    assert order.status == OrderStatus.cancelled and product.stock == 3
    post(client, f"/admin/orders/{order.id}/status", {"status": "new"})
    db.refresh(order)
    assert order.status == OrderStatus.cancelled
    assert post(client, f"/admin/orders/{order.id}/status", {"status": "awaiting_payment"}).status_code == 303


def test_unpaid_card_orders_release_their_stock(client, db, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "payment_demo_mode", True)
    make_user(db, email="sara@example.com")
    product = make_product(db, stock=1)
    login(client, "sara@example.com")
    add(client, product)
    post(client, "/checkout", {**ADDRESS, "payment_method": "card"})
    order = db.exec(select(Order)).one()
    assert order.status == OrderStatus.awaiting_payment
    db.refresh(product)
    assert product.stock == 0

    order.created_at = order.created_at - timedelta(hours=2)
    db.add(order)
    db.commit()
    client.get("/account")
    db.refresh(order)
    db.refresh(product)
    assert order.status == OrderStatus.cancelled and product.stock == 1


def test_deleted_product_keeps_order_history(client, db):
    make_user(db, email="sara@example.com")
    make_user(db, email="admin@example.com", role=Role.admin)
    product = make_product(db, name="قطعة ستُحذف")
    product_id = product.id
    login(client, "sara@example.com")
    add(client, product)
    post(client, "/checkout", ADDRESS)
    order = db.exec(select(Order)).one()
    post(client, "/logout")
    login(client, "admin@example.com")
    post(client, f"/admin/products/{product_id}/delete")
    db.expire_all()
    assert db.get(Product, product_id) is None
    page = client.get(f"/admin/orders/{order.id}")
    assert page.status_code == 200 and "قطعة ستُحذف" in page.text
