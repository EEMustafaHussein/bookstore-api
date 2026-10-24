from fastapi import Depends, HTTPException, Request
from sqlmodel import Session

from app.cart import cart_count, merge_guest_cart
from app.database import get_session
from app.models import User
from app.security import new_token, tokens_match
from app.site_settings import load_site_settings

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# Stripe calls the webhook directly and proves itself with a signature instead.
CSRF_EXEMPT_PATHS = {"/checkout/stripe/webhook"}
FORM_TYPES = ("application/x-www-form-urlencoded", "multipart/form-data")


class LoginRequired(Exception):
    pass


def wants_json(request: Request) -> bool:
    return request.url.path.startswith("/api/") or "application/json" in request.headers.get(
        "accept", ""
    )


def populate_state(request: Request, session: Session) -> None:
    if "csrf" not in request.session:
        request.session["csrf"] = new_token()

    user = None
    user_id = request.session.get("user_id")
    if user_id is not None:
        user = session.get(User, user_id)
        if user is None or not user.is_active:
            request.session.pop("user_id", None)
            user = None
    request.state.user = user
    request.state.site = load_site_settings(session)
    request.state.cart_count = cart_count(session, request)


async def request_context(request: Request, session: Session = Depends(get_session)) -> None:
    """Runs before every page: loads the visitor, shop settings and checks CSRF on form posts."""
    populate_state(request, session)
    if request.method in UNSAFE_METHODS and request.url.path not in CSRF_EXEMPT_PATHS:
        token = request.headers.get("x-csrf-token")
        if token is None and request.headers.get("content-type", "").startswith(FORM_TYPES):
            form = await request.form()
            value = form.get("csrf_token")
            token = value if isinstance(value, str) else None
        if not tokens_match(request.session.get("csrf"), token):
            raise HTTPException(
                status_code=403,
                detail="انتهت صلاحية الصفحة، يرجى تحديثها والمحاولة مرة أخرى",
            )


def current_user(request: Request, _: None = Depends(request_context)) -> User:
    user = request.state.user
    if user is None:
        raise LoginRequired()
    return user


def require_staff(user: User = Depends(current_user)) -> User:
    if not user.is_staff:
        raise HTTPException(status_code=403, detail="هذه الصفحة للمسؤولين فقط")
    return user


def require_owner(user: User = Depends(current_user)) -> User:
    if not user.is_owner:
        raise HTTPException(status_code=403, detail="هذه الصفحة لصاحب المتجر فقط")
    return user


def log_in(request: Request, session: Session, user: User) -> None:
    cart_token = request.session.get("cart_token")
    flashes = request.session.get("_flashes", [])
    # A fresh session on every sign-in; the visitor's cart moves into the account.
    request.session.clear()
    request.session["user_id"] = user.id
    request.session["csrf"] = new_token()
    if flashes:
        request.session["_flashes"] = flashes
    request.state.user = user
    merge_guest_cart(session, cart_token, user.id)
