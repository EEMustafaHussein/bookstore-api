import json
import re

from app.config import Settings, settings
from app.enums import Role, Section
from tests.conftest import login, make_product, make_user, post


def test_sitemap_lists_public_pages_only(client, db, monkeypatch):
    monkeypatch.setattr(settings, "base_url", "https://dreams.example.com/")
    shown = make_product(db, name="فستان")
    hidden = make_product(db, name="مسودة", published=False)
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    body = response.text
    assert "<loc>https://dreams.example.com/</loc>" in body
    assert "<loc>https://dreams.example.com/bala</loc>" in body
    assert f"<loc>https://dreams.example.com/product/{shown.id}</loc>" in body
    assert f"/product/{hidden.id}<" not in body
    assert "<loc>https://dreams.example.com/shop?section=new</loc>" in body
    assert "Sitemap: https://dreams.example.com/sitemap.xml" in client.get("/robots.txt").text


def test_product_page_has_structured_data(client, db, monkeypatch):
    monkeypatch.setattr(settings, "base_url", "https://dreams.example.com")
    product = make_product(db, name='جاكيت "بالة"', price=15000, section=Section.bala, stock=1)
    page = client.get(f"/product/{product.id}").text
    raw = re.search(r'<script type="application/ld\+json">(.*?)</script>', page, re.S).group(1)
    data = json.loads(raw)
    assert data["@type"] == "Product" and data["name"] == 'جاكيت "بالة"'
    assert data["offers"]["price"] == 15000 and data["offers"]["priceCurrency"] == "IQD"
    assert data["offers"]["itemCondition"].endswith("UsedCondition")
    home = client.get("/").text
    assert '"@type": "ClothingStore"' in home or '"@type":"ClothingStore"' in home


def test_owner_sets_google_verification(client, db):
    make_user(db, email="owner@example.com", role=Role.owner)
    login(client, "owner@example.com")
    post(
        client,
        "/admin/settings",
        {
            "site_name": "ملابس الأحلام",
            "shipping_fee": "5000",
            "free_shipping_over": "0",
            "google_verification": '<meta name="google-site-verification" content="AbC_123-xyz987" />',
        },
    )
    assert '<meta name="google-site-verification" content="AbC_123-xyz987">' in client.get("/").text

    post(client, "/admin/settings", {"site_name": "ملابس الأحلام", "google_verification": '"><script>'})
    assert "google-site-verification" not in client.get("/").text


def test_base_url_falls_back_to_render_address(monkeypatch):
    monkeypatch.delenv("BASE_URL", raising=False)
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://dreams-store.onrender.com")
    assert Settings().base_url == "https://dreams-store.onrender.com"
    monkeypatch.setenv("BASE_URL", "https://dreams.example.com")
    assert Settings().base_url == "https://dreams.example.com"
