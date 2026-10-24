from app.enums import Section
from tests.conftest import make_product, post


def test_public_pages_render(client, db):
    make_product(db, name="فستان مخمل")
    make_product(db, name="جاكيت بالة", section=Section.bala, stock=1)
    for url in ["/", "/shop", "/shop?section=new", "/bala", "/about", "/login", "/register", "/cart"]:
        response = client.get(url)
        assert response.status_code == 200, url
        assert "ملابس الأحلام" in response.text
    home = client.get("/").text
    assert "فستان مخمل" in home and "جاكيت بالة" in home
    assert "جاكيت بالة" in client.get("/bala").text
    assert "فستان مخمل" not in client.get("/bala").text


def test_security_headers_and_robots(client):
    response = client.get("/")
    assert response.headers["x-frame-options"] == "DENY"
    assert "script-src 'self'" in response.headers["content-security-policy"]
    assert "Disallow: /admin" in client.get("/robots.txt").text


def test_not_found_pages_are_friendly(client, db):
    for url in ["/nope", "/product/999", "/product/abc", "/product/99999999999999999999"]:
        response = client.get(url)
        assert response.status_code == 404, url
        assert "غير موجود" in response.text


def test_hidden_products_are_not_public(client, db):
    product = make_product(db, name="مسودة", published=False)
    assert client.get(f"/product/{product.id}").status_code == 404
    assert "مسودة" not in client.get("/shop").text


def test_search_filters_and_pagination(client, db):
    for index in range(30):
        make_product(db, name=f"بلوزة رقم {index}", price=10000 + index)
    make_product(db, name="عباية سوداء")
    response = client.get("/shop?q=عباية")
    assert "عباية سوداء" in response.text and "بلوزة رقم" not in response.text
    page_two = client.get("/shop?page=2&sort=price_asc")
    assert page_two.status_code == 200
    assert client.get("/shop?page=99999999&category=abc&sort=bad").status_code == 200
    assert client.get("/shop?q=%25_%5C").status_code == 200


def test_user_text_is_escaped(client, db):
    product = make_product(db, name='<script>alert("x")</script>')
    page = client.get(f"/product/{product.id}").text
    assert '<script>alert("x")</script>' not in page
    assert "&lt;script&gt;" in page


def test_forms_require_csrf_token(client, db):
    product = make_product(db)
    response = client.post("/cart/add", data={"product_id": product.id}, follow_redirects=False)
    assert response.status_code == 403
    response = client.post(
        "/cart/add", data={"product_id": product.id, "csrf_token": "wrong"}, follow_redirects=False
    )
    assert response.status_code == 403
    assert post(client, "/cart/add", {"product_id": product.id}).status_code == 303
