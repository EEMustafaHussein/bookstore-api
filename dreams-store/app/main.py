import logging
import os
from contextlib import asynccontextmanager
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app.config import BASE_DIR, settings
from app.database import create_db_and_tables, engine
from app.deps import LoginRequired, populate_state, wants_json
from app.enums import Role
from app.forms import email as normalize_email
from app.models import User
from app.routers import account, admin, auth, cart, checkout, media, owner, public
from app.security import hash_password
from app.templating import render

logger = logging.getLogger("dreams")

CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "img-src 'self' data: blob:",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com",
        "script-src 'self'",
        "connect-src 'self'",
        "form-action 'self' https://checkout.stripe.com",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "object-src 'none'",
    ]
)
MAX_BODY_BYTES = 90 * 1024 * 1024


def bootstrap_owner() -> None:
    """Creates the owner account from OWNER_EMAIL / OWNER_PASSWORD the first time the shop starts."""
    email = normalize_email(settings.owner_email or "")
    if not email or not settings.owner_password:
        return
    with Session(engine) as session:
        if session.exec(select(User).where(User.role == Role.owner)).first():
            return
        user = session.exec(select(User).where(User.email == email)).first()
        if user is None:
            user = User(
                name=settings.owner_name,
                email=email,
                hashed_password=hash_password(settings.owner_password),
            )
        user.role = Role.owner
        user.is_active = True
        session.add(user)
        session.commit()
        logger.info("Owner account ready: %s", email)


def check_hosting() -> None:
    """Render wipes files on every restart, so an SQLite file there would lose the whole shop."""
    on_render = bool(os.environ.get("RENDER"))
    if on_render and settings.database_url.startswith("sqlite") and "/var/data/" not in settings.database_url:
        raise RuntimeError(
            "DATABASE_URL is not set: on Render the shop needs a PostgreSQL database "
            "(for example a free Neon link), otherwise every restart deletes all products and orders. "
            "ضع رابط قاعدة البيانات في DATABASE_URL."
        )
    if on_render and settings.media_storage == "disk" and not str(settings.media_dir).startswith("/var/data"):
        raise RuntimeError(
            "MEDIA_STORAGE must be 'database' on Render without a disk, otherwise uploaded photos are lost."
        )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    check_hosting()
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    create_db_and_tables()
    bootstrap_owner()
    yield


class SecurityHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        length = dict(scope.get("headers") or []).get(b"content-length")
        if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
            response = JSONResponse({"detail": "الملفات المرفوعة كبيرة جداً"}, status_code=413)
            await response(scope, receive, send)
            return

        if scope["method"] == "HEAD":
            # Health checks and link previews ask with HEAD: answer as for GET.
            # The server itself leaves the body out of a HEAD reply.
            scope = dict(scope, method="GET")

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers += [
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"strict-origin-when-cross-origin"),
                    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                    (b"content-security-policy", CONTENT_SECURITY_POLICY.encode()),
                ]
                if settings.cookie_secure:
                    headers.append((b"strict-transport-security", b"max-age=31536000"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


settings.media_dir.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="ملابس الأحلام",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="dreams_session",
    same_site="lax",
    https_only=settings.cookie_secure,
)
app.add_middleware(SecurityHeadersMiddleware)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

for module in (public, auth, cart, checkout, account, admin, owner):
    app.include_router(module.router)
app.include_router(checkout.webhook_router)
app.include_router(media.router)


def _error_page(request: Request, status_code: int, message: str):
    if wants_json(request):
        return JSONResponse({"ok": False, "message": message, "detail": message}, status_code=status_code)
    if not hasattr(request.state, "site"):
        # The error happened before the page loaded the visitor, so load them here.
        with Session(engine) as session:
            try:
                populate_state(request, session)
            except Exception:  # noqa: BLE001 - an error page must render even if the database is down
                logger.exception("Could not load page state for error page")
    titles = {
        400: "طلب غير صالح",
        403: "غير مسموح",
        404: "الصفحة غير موجودة",
        405: "طلب غير صالح",
        413: "الملفات كبيرة جداً",
        429: "محاولات كثيرة",
        500: "حدث خطأ غير متوقع",
    }
    return render(
        request,
        "errors/error.html",
        {"code": status_code, "title": titles.get(status_code, "حدث خطأ"), "message": message},
        status_code=status_code,
    )


@app.exception_handler(LoginRequired)
async def login_required_handler(request: Request, _exc: LoginRequired):
    if wants_json(request):
        return JSONResponse({"ok": False, "message": "يرجى تسجيل الدخول أولاً"}, status_code=401)
    target = request.url.path
    if request.method == "GET" and request.url.query:
        target += "?" + request.url.query
    return RedirectResponse(f"/login?next={quote(target, safe='')}", status_code=303)


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    defaults = {404: "الصفحة المطلوبة غير موجودة أو تم نقلها.", 405: "هذا الطلب غير مدعوم."}
    message = exc.detail if isinstance(exc.detail, str) and exc.detail not in (
        "Not Found",
        "Method Not Allowed",
    ) else defaults.get(exc.status_code, "تعذّر إكمال الطلب.")
    return _error_page(request, exc.status_code, message)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, _exc: RequestValidationError):
    if request.method == "GET":
        return _error_page(request, 404, "الصفحة المطلوبة غير موجودة أو تم نقلها.")
    return _error_page(request, 400, "البيانات المرسلة غير صحيحة.")


@app.exception_handler(Exception)
async def server_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url.path, exc_info=exc)
    return _error_page(request, 500, "حدث خطأ غير متوقع، يرجى المحاولة مرة أخرى بعد قليل.")
