from datetime import datetime, timedelta, timezone
from functools import lru_cache

from fastapi import Request
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context
from markupsafe import Markup, escape

from app.config import BASE_DIR, settings
from app.enums import (
    ADMIN_ORDER_STATUSES,
    GOVERNORATES,
    ORDER_STATUS_LABELS,
    PAYMENT_METHOD_LABELS,
    PAYMENT_STATUS_LABELS,
    ROLE_LABELS,
    SECTION_LABELS,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    Role,
    Section,
)
from app.site_settings import DEFAULTS, SOCIAL_PLATFORMS

# Iraq has used UTC+3 all year since 2008.
LOCAL_TZ = timezone(timedelta(hours=3))
STATIC_DIR = BASE_DIR / "static"


def flash(request: Request, message: str, category: str = "success") -> None:
    messages = request.session.get("_flashes", [])
    messages.append({"message": message, "category": category})
    request.session["_flashes"] = messages[-5:]


def _context(request: Request) -> dict:
    state = request.state
    return {
        "site": getattr(state, "site", DEFAULTS),
        "current_user": getattr(state, "user", None),
        "cart_count": getattr(state, "cart_count", 0),
        "csrf_token": request.session.get("csrf", ""),
        "flashes": request.session.pop("_flashes", []),
    }


templates = Jinja2Templates(directory=BASE_DIR / "templates", context_processors=[_context])
env = templates.env


def format_money(value, site: dict) -> str:
    try:
        amount = int(value or 0)
    except (TypeError, ValueError):
        amount = 0
    return f"{amount:,} {site.get('currency_symbol', '')}".strip()


@pass_context
def money(context, value) -> str:
    return format_money(value, context.get("site", DEFAULTS))


def media_url(name: str | None, fallback: str = "img/placeholder.svg") -> str:
    if not name:
        return asset(fallback)
    return f"/media/{name}"


@lru_cache(maxsize=256)
def _asset_version(path: str) -> str:
    try:
        return str(int((STATIC_DIR / path).stat().st_mtime))
    except OSError:
        return "0"


def asset(path: str) -> str:
    version = "dev" if settings.debug else _asset_version(path)
    return f"/static/{path}?v={version}"


def local_dt(value: datetime | None, fmt: str = "%Y/%m/%d — %I:%M %p") -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    text = value.astimezone(LOCAL_TZ).strftime(fmt)
    return text.replace("AM", "ص").replace("PM", "م")


def nl2br(value: str | None) -> Markup:
    if not value:
        return Markup("")
    return Markup("<br>").join(escape(line) for line in str(value).splitlines())


def initials(name: str | None) -> str:
    parts = [p for p in (name or "").split() if p]
    if not parts:
        return "✦"
    return "".join(p[0] for p in parts[:2])


env.filters.update(money=money, media=media_url, local_dt=local_dt, nl2br=nl2br, initials=initials)
env.globals.update(
    asset=asset,
    settings=settings,
    now=lambda: datetime.now(LOCAL_TZ),
    Role=Role,
    Section=Section,
    OrderStatus=OrderStatus,
    PaymentMethod=PaymentMethod,
    PaymentStatus=PaymentStatus,
    ROLE_LABELS=ROLE_LABELS,
    SECTION_LABELS=SECTION_LABELS,
    ORDER_STATUS_LABELS=ORDER_STATUS_LABELS,
    PAYMENT_METHOD_LABELS=PAYMENT_METHOD_LABELS,
    PAYMENT_STATUS_LABELS=PAYMENT_STATUS_LABELS,
    ADMIN_ORDER_STATUSES=ADMIN_ORDER_STATUSES,
    GOVERNORATES=GOVERNORATES,
    SOCIAL_PLATFORMS=SOCIAL_PLATFORMS,
)


def render(request: Request, name: str, context: dict | None = None, status_code: int = 200):
    return templates.TemplateResponse(request, name, context or {}, status_code=status_code)
