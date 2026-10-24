from app.enums import Role
from tests.conftest import image_file, login, make_user, post


def test_owner_edits_settings_and_social_links(client, db):
    make_user(db, email="owner@example.com", role=Role.owner)
    login(client, "owner@example.com")
    response = post(
        client,
        "/admin/settings",
        {
            "site_name": "ملابس الأحلام",
            "tagline": "أناقة كل يوم",
            "announcement": "خصم 20% هذا الأسبوع",
            "hero_title": "ارتدي أحلامكِ",
            "hero_subtitle": "نص",
            "shipping_fee": "6,000",
            "free_shipping_over": "0",
            "currency_symbol": "د.ع",
            "social_instagram": "instagram.com/dreams",
            "social_facebook": "javascript:alert(1)",
            "social_whatsapp": "0770 123 4567",
            "social_tiktok": "",
        },
    )
    assert response.status_code == 303
    home = client.get("/").text
    assert "خصم 20% هذا الأسبوع" in home
    assert 'href="https://instagram.com/dreams"' in home
    assert 'href="https://wa.me/9647701234567"' in home
    assert "javascript:" not in home.split("<footer", 1)[1]


def test_owner_edits_about_page(client, db):
    make_user(db, email="owner@example.com", role=Role.owner)
    login(client, "owner@example.com")
    response = post(
        client,
        "/admin/about",
        {
            "name": "علي حسين",
            "title": "مهندس كهرباء ومطوّر مواقع",
            "bio": "خريج الجامعة المستنصرية",
            "phone": "07801112233",
            "email": "ali@example.com",
            "location": "بغداد",
            "skills": "Python, FastAPI",
            "website_label_0": "معرض أعمالي",
            "website_url_0": "ali.dev",
            "website_url_1": "",
        },
        files=[("photo", image_file("me.jpg"))],
    )
    assert response.status_code == 303
    page = client.get("/about").text
    for text in ["علي حسين", "خريج الجامعة المستنصرية", "07801112233", "https://ali.dev", "معرض أعمالي", "https://wa.me/9647801112233", "/media/about/"]:
        assert text in page, text
    assert "تصميم وتطوير" in page and "علي حسين" in client.get("/").text
