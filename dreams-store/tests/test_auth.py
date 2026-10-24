import os

from sqlmodel import select

from app.enums import Role
from app.main import bootstrap_owner
from app.models import User
from tests.conftest import PASSWORD, login, make_user, post


def test_register_logs_in_and_rejects_duplicates(client, db):
    response = post(
        client,
        "/register",
        {"name": "سارة", "email": "Sara@Example.com", "password": PASSWORD, "password_confirm": PASSWORD, "phone": "0770 123 4567"},
    )
    assert response.status_code == 303
    user = db.exec(select(User).where(User.email == "sara@example.com")).one()
    assert user.role == Role.customer and user.phone == "07701234567"
    assert client.get("/account").status_code == 200

    post(client, "/logout")
    again = post(
        client,
        "/register",
        {"name": "سارة", "email": "sara@example.com", "password": PASSWORD, "password_confirm": PASSWORD},
    )
    assert again.status_code == 400
    assert "مسجّل مسبقاً" in again.text


def test_register_validation_messages(client):
    response = post(
        client,
        "/register",
        {"name": "", "email": "bad", "password": "short", "password_confirm": "x", "phone": "123"},
    )
    assert response.status_code == 400
    for message in ["اكتبي اسمكِ", "البريد الإلكتروني غير صحيح", "8 أحرف", "رقم الهاتف غير صحيح"]:
        assert message in response.text


def test_login_logout_and_wrong_password(client, db):
    make_user(db, email="mona@example.com")
    bad = post(client, "/login", {"email": "mona@example.com", "password": "nope12345"})
    assert bad.status_code == 400 and "غير صحيحة" in bad.text
    unknown = post(client, "/login", {"email": "ghost@example.com", "password": PASSWORD})
    assert unknown.status_code == 400

    login(client, "MONA@example.com")
    assert client.get("/account").status_code == 200
    post(client, "/logout")
    assert client.get("/account", follow_redirects=False).headers["location"].startswith("/login")


def test_login_rate_limit(client, db):
    make_user(db, email="mona@example.com")
    for _ in range(8):
        post(client, "/login", {"email": "mona@example.com", "password": "wrong-pass1"})
    blocked = post(client, "/login", {"email": "mona@example.com", "password": PASSWORD})
    assert blocked.status_code == 429


def test_disabled_account_cannot_log_in(client, db):
    make_user(db, email="off@example.com", active=False)
    response = post(client, "/login", {"email": "off@example.com", "password": PASSWORD})
    assert response.status_code == 403


def test_login_redirect_stays_on_site(client, db):
    make_user(db, email="mona@example.com")
    response = post(client, "/login", {"email": "mona@example.com", "password": PASSWORD, "next": "//evil.example"})
    assert response.headers["location"] == "/"
    post(client, "/logout")
    response = post(client, "/login", {"email": "mona@example.com", "password": PASSWORD, "next": "/checkout"})
    assert response.headers["location"] == "/checkout"


def test_staff_land_on_dashboard(client, db):
    make_user(db, email="boss@example.com", role=Role.owner)
    response = login(client, "boss@example.com")
    assert response.headers["location"] == "/admin"


def test_change_password(client, db):
    make_user(db, email="mona@example.com")
    login(client, "mona@example.com")
    post(client, "/account/password", {"current_password": PASSWORD, "new_password": "NewPass456", "new_password_confirm": "NewPass456"})
    post(client, "/logout")
    assert post(client, "/login", {"email": "mona@example.com", "password": PASSWORD}).status_code == 400
    login(client, "mona@example.com", "NewPass456")


def test_owner_bootstrap_from_environment(db, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "owner_email", "Owner@Example.com")
    monkeypatch.setattr(settings, "owner_password", "OwnerPass1")
    bootstrap_owner()
    bootstrap_owner()
    owners = db.exec(select(User).where(User.role == Role.owner)).all()
    assert len(owners) == 1 and owners[0].email == "owner@example.com"
    assert os.environ.get("OWNER_EMAIL") == ""
