from sqlmodel import select

from app.enums import Role
from app.models import User
from tests.conftest import PASSWORD, login, make_user, post

STAFF_PAGES = ["/admin", "/admin/products", "/admin/products/new", "/admin/categories", "/admin/orders"]
OWNER_PAGES = ["/admin/team", "/admin/settings", "/admin/about"]


def test_visitors_are_sent_to_login(client):
    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=%2Fadmin"


def test_customer_cannot_open_dashboard(client, db):
    make_user(db, email="c@example.com")
    login(client, "c@example.com")
    for url in STAFF_PAGES + OWNER_PAGES:
        assert client.get(url).status_code == 403, url


def test_admin_manages_shop_but_not_admins(client, db):
    make_user(db, email="admin@example.com", role=Role.admin, name="مسؤول")
    customer = make_user(db, email="c@example.com")
    login(client, "admin@example.com")
    for url in STAFF_PAGES:
        assert client.get(url).status_code == 200, url
    for url in OWNER_PAGES:
        assert client.get(url).status_code == 403, url

    response = post(client, "/admin/team/admins", {"name": "x", "email": "new@example.com", "password": PASSWORD})
    assert response.status_code == 403
    assert post(client, f"/admin/team/{customer.id}/role", {"role": "admin"}).status_code == 403
    db.refresh(customer)
    assert customer.role == Role.customer
    assert db.exec(select(User).where(User.email == "new@example.com")).first() is None


def test_owner_adds_and_removes_admins(client, db):
    owner = make_user(db, email="owner@example.com", role=Role.owner, name="صاحب المتجر")
    login(client, "owner@example.com")
    for url in STAFF_PAGES + OWNER_PAGES:
        assert client.get(url).status_code == 200, url

    response = post(client, "/admin/team/admins", {"name": "نور", "email": "Noor@Example.com", "password": "AdminPass1"})
    assert response.status_code == 303
    admin = db.exec(select(User).where(User.email == "noor@example.com")).one()
    assert admin.role == Role.admin

    post(client, "/logout")
    login(client, "noor@example.com", "AdminPass1")
    assert client.get("/admin/products").status_code == 200
    post(client, "/logout")

    login(client, "owner@example.com")
    post(client, f"/admin/team/{admin.id}/role", {"role": "customer"})
    db.refresh(admin)
    assert admin.role == Role.customer

    # The owner account itself is protected.
    post(client, f"/admin/team/{owner.id}/role", {"role": "customer"})
    post(client, f"/admin/team/{owner.id}/active")
    db.refresh(owner)
    assert owner.role == Role.owner and owner.is_active


def test_removed_admin_loses_access_immediately(client, db):
    admin = make_user(db, email="admin@example.com", role=Role.admin)
    login(client, "admin@example.com")
    assert client.get("/admin").status_code == 200
    admin.role = Role.customer
    db.add(admin)
    db.commit()
    assert client.get("/admin").status_code == 403


def test_owner_can_promote_disable_and_reset_password(client, db):
    make_user(db, email="owner@example.com", role=Role.owner)
    customer = make_user(db, email="c@example.com")
    login(client, "owner@example.com")

    post(client, f"/admin/team/{customer.id}/role", {"role": "admin"})
    db.refresh(customer)
    assert customer.role == Role.admin

    post(client, f"/admin/team/{customer.id}/password", {"password": "Fresh1234"})
    post(client, f"/admin/team/{customer.id}/active")
    db.refresh(customer)
    assert not customer.is_active

    post(client, "/logout")
    assert post(client, "/login", {"email": "c@example.com", "password": "Fresh1234"}).status_code == 403


def test_duplicate_admin_email_is_rejected(client, db):
    make_user(db, email="owner@example.com", role=Role.owner)
    make_user(db, email="c@example.com")
    login(client, "owner@example.com")
    post(client, "/admin/team/admins", {"name": "x", "email": "c@example.com", "password": PASSWORD})
    assert db.exec(select(User).where(User.email == "c@example.com")).one().role == Role.customer
