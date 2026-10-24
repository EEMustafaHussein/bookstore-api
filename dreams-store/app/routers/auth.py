from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app import forms
from app.database import get_session
from app.deps import log_in, request_context
from app.models import User
from app.security import (
    DUMMY_HASH,
    hash_password,
    login_limiter,
    password_problem,
    verify_password,
)
from app.templating import flash, render

router = APIRouter(dependencies=[Depends(request_context)])


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _after_login(user: User, next_url: str) -> RedirectResponse:
    default = "/admin" if user.is_staff else "/"
    return RedirectResponse(forms.safe_next(next_url, default), status_code=303)


@router.get("/register")
def register_page(request: Request):
    if request.state.user:
        return RedirectResponse("/account", status_code=303)
    return render(request, "auth/register.html", {"values": {}, "errors": {}})


@router.post("/register")
async def register(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    values = {
        "name": forms.text(form, "name", 80),
        "email": forms.text(form, "email", 254),
        "phone": forms.text(form, "phone", 20),
    }
    password = forms.secret(form, "password")
    confirm = forms.secret(form, "password_confirm")
    next_url = forms.text(form, "next", 300)

    errors = {}
    if len(values["name"]) < 2:
        errors["name"] = "اكتبي اسمكِ"
    email = forms.email(values["email"])
    if email is None:
        errors["email"] = "البريد الإلكتروني غير صحيح"
    elif session.exec(select(User).where(User.email == email)).first():
        errors["email"] = "هذا البريد مسجّل مسبقاً، سجّلي الدخول بدلاً من ذلك"
    phone = ""
    if values["phone"]:
        phone = forms.iraqi_mobile(values["phone"]) or ""
        if not phone:
            errors["phone"] = "رقم الهاتف غير صحيح، مثال: 07701234567"
    problem = password_problem(password)
    if problem:
        errors["password"] = problem
    elif password != confirm:
        errors["password_confirm"] = "كلمتا المرور غير متطابقتين"

    if errors:
        return render(
            request,
            "auth/register.html",
            {"values": values, "errors": errors, "next": next_url},
            status_code=400,
        )

    user = User(name=values["name"], email=email, phone=phone, hashed_password=hash_password(password))
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        errors["email"] = "هذا البريد مسجّل مسبقاً، سجّلي الدخول بدلاً من ذلك"
        return render(
            request,
            "auth/register.html",
            {"values": values, "errors": errors, "next": next_url},
            status_code=400,
        )
    session.refresh(user)
    log_in(request, session, user)
    flash(request, f"أهلاً بكِ يا {user.name} ✨ تم إنشاء حسابكِ بنجاح")
    return _after_login(user, next_url)


@router.get("/login")
def login_page(request: Request):
    if request.state.user:
        return RedirectResponse("/account", status_code=303)
    next_url = forms.safe_next(request.query_params.get("next"), "")
    return render(request, "auth/login.html", {"values": {}, "error": None, "next": next_url})


@router.post("/login")
async def login(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    email_input = forms.text(form, "email", 254)
    password = forms.secret(form, "password")
    next_url = forms.text(form, "next", 300)
    context = {"values": {"email": email_input}, "next": next_url}

    key = _client_key(request)
    if login_limiter.is_blocked(key):
        context["error"] = "محاولات كثيرة، يرجى الانتظار ربع ساعة ثم المحاولة مجدداً"
        return render(request, "auth/login.html", context, status_code=429)

    email = forms.email(email_input)
    user = session.exec(select(User).where(User.email == email)).first() if email else None
    if user is None:
        verify_password(password or "x", DUMMY_HASH)
        valid = False
    else:
        valid = verify_password(password, user.hashed_password)

    if not valid:
        login_limiter.record_failure(key)
        context["error"] = "البريد الإلكتروني أو كلمة المرور غير صحيحة"
        return render(request, "auth/login.html", context, status_code=400)
    if not user.is_active:
        context["error"] = "هذا الحساب موقوف، يرجى التواصل مع إدارة المتجر"
        return render(request, "auth/login.html", context, status_code=403)

    login_limiter.reset(key)
    log_in(request, session, user)
    flash(request, f"أهلاً بعودتك يا {user.name} 🌸")
    return _after_login(user, next_url)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    flash(request, "تم تسجيل الخروج، نراكِ قريباً")
    return RedirectResponse("/", status_code=303)
