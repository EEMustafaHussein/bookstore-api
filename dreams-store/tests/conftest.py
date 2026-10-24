import io
import os
import re
import shutil
import tempfile
from pathlib import Path

MEDIA_DIR = Path(tempfile.mkdtemp(prefix="dreams-media-"))
os.environ.update(
    SECRET_KEY="test-secret-key-that-is-long-enough-123456",
    DATABASE_URL="sqlite://",
    MEDIA_DIR=str(MEDIA_DIR),
    PAYMENT_DEMO_MODE="false",
    STRIPE_SECRET_KEY="",
    STRIPE_WEBHOOK_SECRET="",
    OWNER_EMAIL="",
    OWNER_PASSWORD="",
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402
from sqlmodel import Session, SQLModel  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import engine  # noqa: E402
from app.enums import Role, Section  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Product, User  # noqa: E402
from app.security import hash_password, login_limiter  # noqa: E402

PASSWORD = "Secret123!"
CSRF_RE = re.compile(r'name="csrf-token" content="([^"]+)"')


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    login_limiter._failures.clear()
    for child in MEDIA_DIR.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
    monkeypatch.setattr(settings, "payment_demo_mode", False)
    monkeypatch.setattr(settings, "stripe_secret_key", None)
    monkeypatch.setattr(settings, "stripe_webhook_secret", None)
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db():
    with Session(engine) as session:
        yield session


def csrf(client) -> str:
    page = client.get("/login")
    match = CSRF_RE.search(page.text)
    assert match, "csrf token not found"
    return match.group(1)


def post(client, url, data=None, files=None, **kwargs):
    data = dict(data or {})
    data["csrf_token"] = csrf(client)
    return client.post(url, data=data, files=files, follow_redirects=False, **kwargs)


def make_user(db, email="customer@example.com", role=Role.customer, name="زبونة", active=True) -> User:
    user = User(name=name, email=email, hashed_password=hash_password(PASSWORD), role=role, is_active=active)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login(client, email, password=PASSWORD):
    response = post(client, "/login", {"email": email, "password": password})
    assert response.status_code == 303, response.text
    return response


def make_product(db, name="فستان وردي", price=25000, stock=3, sizes="", colors="", section=Section.new, published=True) -> Product:
    product = Product(
        name=name, price=price, stock=stock, sizes=sizes, colors=colors, section=section, is_published=published
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def image_file(name="photo.jpg", color=(230, 160, 180), size=(800, 1000), fmt="JPEG"):
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, fmt)
    buffer.seek(0)
    content_type = "image/png" if fmt == "PNG" else "image/jpeg"
    return (name, buffer, content_type)
