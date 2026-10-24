"""Pages only the shop owner can open: the team of admins, shop settings and the about page."""

import math

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app import forms
from app.database import get_by_id, get_session
from app.deps import request_context, require_owner
from app.enums import Role
from app.images import ImageError, delete_image, save_image, uploaded_files
from app.models import User
from app.security import hash_password, password_problem
from app.site_settings import MAX_WEBSITES, SOCIAL_PLATFORMS, save_site_settings
from app.templating import flash, render

router = APIRouter(
    prefix="/admin", dependencies=[Depends(request_context), Depends(require_owner)]
)

PAGE_SIZE = 50


# ---------------------------------------------------------------- team


@router.get("/team")
def team(request: Request, session: Session = Depends(get_session)):
    params = request.query_params
    statement = select(User)
    role = params.get("role")
    if role in Role._value2member_map_:
        statement = statement.where(User.role == Role(role))
    query = params.get("q", "").strip()[:80]
    if query:
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        statement = statement.where(
            or_(
                User.name.ilike(f"%{escaped}%", escape="\\"),
                User.email.ilike(f"%{escaped}%", escape="\\"),
                User.phone.ilike(f"%{escaped}%", escape="\\"),
            )
        )
    total = session.exec(select(func.count()).select_from(statement.subquery())).one()
    pages = max(math.ceil(total / PAGE_SIZE), 1)
    raw_page = params.get("page", "1")
    page = min(max(int(raw_page), 1) if raw_page.isdigit() and len(raw_page) <= 6 else 1, pages)
    users = session.exec(
        statement.order_by(User.role, User.created_at.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    ).all()
    admins = session.exec(
        select(User).where(User.role.in_([Role.owner, Role.admin])).order_by(User.role, User.name)
    ).all()
    filters = {k: v for k, v in params.items() if k in ("q", "role") and v}
    return render(
        request,
        "admin/team.html",
        {
            "active": "team",
            "users": users,
            "admins": admins,
            "total": total,
            "page": page,
            "pages": pages,
            "filters": filters,
        },
    )


def _member_or_404(session: Session, user_id: int) -> User:
    user = get_by_id(session, User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="الحساب غير موجود")
    return user


def _team_redirect() -> RedirectResponse:
    return RedirectResponse("/admin/team", status_code=303)


@router.post("/team/admins")
async def create_admin(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    name = forms.text(form, "name", 80)
    email = forms.email(forms.text(form, "email", 254))
    password = forms.secret(form, "password")
    problem = password_problem(password)

    if len(name) < 2:
        flash(request, "اكتب اسم المسؤول", "error")
    elif email is None:
        flash(request, "البريد الإلكتروني غير صحيح", "error")
    elif problem:
        flash(request, problem, "error")
    else:
        existing = session.exec(select(User).where(User.email == email)).first()
        if existing is not None:
            flash(
                request,
                "هذا البريد مسجّل مسبقاً — استخدم زر «اجعله مسؤولاً» بجانب الحساب في القائمة",
                "error",
            )
            return _team_redirect()
        session.add(User(name=name, email=email, hashed_password=hash_password(password), role=Role.admin))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            flash(request, "هذا البريد مسجّل مسبقاً", "error")
            return _team_redirect()
        flash(request, f"تمت إضافة «{name}» كمسؤول، يمكنه الدخول الآن ببريده وكلمة المرور")
    return _team_redirect()


@router.post("/team/{user_id}/role")
async def change_role(user_id: int, request: Request, session: Session = Depends(get_session)):
    member = _member_or_404(session, user_id)
    form = await request.form()
    target = forms.text(form, "role", 20)
    if member.is_owner:
        flash(request, "لا يمكن تغيير صلاحيات صاحب المتجر", "error")
    elif target not in (Role.admin.value, Role.customer.value):
        flash(request, "صلاحية غير صحيحة", "error")
    else:
        member.role = Role(target)
        session.add(member)
        session.commit()
        if member.role == Role.admin:
            flash(request, f"أصبح «{member.name}» مسؤولاً")
        else:
            flash(request, f"تمت إزالة «{member.name}» من المسؤولين")
    return _team_redirect()


@router.post("/team/{user_id}/active")
def toggle_active(user_id: int, request: Request, session: Session = Depends(get_session)):
    member = _member_or_404(session, user_id)
    if member.is_owner:
        flash(request, "لا يمكن إيقاف حساب صاحب المتجر", "error")
        return _team_redirect()
    member.is_active = not member.is_active
    session.add(member)
    session.commit()
    flash(request, f"تم تفعيل حساب «{member.name}»" if member.is_active else f"تم إيقاف حساب «{member.name}»")
    return _team_redirect()


@router.post("/team/{user_id}/password")
async def reset_password(user_id: int, request: Request, session: Session = Depends(get_session)):
    member = _member_or_404(session, user_id)
    form = await request.form()
    password = forms.secret(form, "password")
    problem = password_problem(password)
    if member.is_owner and member.id != request.state.user.id:
        flash(request, "لا يمكن تغيير كلمة مرور صاحب المتجر", "error")
    elif problem:
        flash(request, problem, "error")
    else:
        member.hashed_password = hash_password(password)
        session.add(member)
        session.commit()
        flash(request, f"تم تعيين كلمة مرور جديدة لـ «{member.name}»")
    return _team_redirect()


# ---------------------------------------------------------------- settings


def _whatsapp_link(value: str) -> str:
    digits = "".join(ch for ch in forms.western_digits(value) if ch.isdigit())
    if digits and len(digits) >= 8 and not value.strip().lower().startswith(("http", "wa.me")):
        if digits.startswith("07") and len(digits) == 11:
            digits = "964" + digits[1:]
        elif digits.startswith("00"):
            digits = digits[2:]
        return f"https://wa.me/{digits}"
    return forms.safe_url(value)


@router.get("/settings")
def settings_page(request: Request):
    return render(request, "admin/settings.html", {"active": "settings"})


@router.post("/settings")
async def save_settings(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    try:
        shipping_fee = forms.number(form, "shipping_fee") or 0
        free_over = forms.number(form, "free_shipping_over") or 0
    except ValueError:
        flash(request, "اكتب أجور التوصيل بالأرقام", "error")
        return RedirectResponse("/admin/settings", status_code=303)

    site_name = forms.text(form, "site_name", 60)
    if len(site_name) < 2:
        flash(request, "اكتب اسم المتجر", "error")
        return RedirectResponse("/admin/settings", status_code=303)

    contact_email = forms.text(form, "contact_email", 254)
    social = {}
    for key, _label in SOCIAL_PLATFORMS:
        value = forms.text(form, f"social_{key}", 300)
        social[key] = _whatsapp_link(value) if key == "whatsapp" else forms.safe_url(value)

    save_site_settings(
        session,
        {
            "site_name": site_name,
            "tagline": forms.text(form, "tagline", 120),
            "announcement": forms.text(form, "announcement", 200),
            "hero_title": forms.text(form, "hero_title", 60) or "ارتدي أحلامكِ",
            "hero_subtitle": forms.text(form, "hero_subtitle", 250),
            "contact_phone": forms.text(form, "contact_phone", 30),
            "contact_email": (forms.email(contact_email) or "") if contact_email else "",
            "address": forms.text(form, "address", 150),
            "currency_symbol": forms.text(form, "currency_symbol", 10) or "د.ع",
            "shipping_fee": min(shipping_fee, 10_000_000),
            "free_shipping_over": min(free_over, 1_000_000_000),
            "social": social,
        },
    )
    flash(request, "تم حفظ إعدادات المتجر ✨")
    return RedirectResponse("/admin/settings", status_code=303)


# ---------------------------------------------------------------- about page


@router.get("/about")
def about_page(request: Request):
    about = request.state.site["about"]
    websites = list(about.get("websites") or [])
    websites += [{"label": "", "url": ""}] * (MAX_WEBSITES - len(websites))
    return render(request, "admin/about.html", {"active": "about", "websites": websites[:MAX_WEBSITES]})


@router.post("/about")
async def save_about(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    current = request.state.site["about"]
    photo = current.get("photo")
    old_photo = photo

    uploads = uploaded_files(form, "photo")
    if uploads:
        try:
            photo = save_image(uploads[0], "about", max_side=900)
        except ImageError as exc:
            flash(request, str(exc), "error")
            return RedirectResponse("/admin/about", status_code=303)
    elif forms.checkbox(form, "remove_photo"):
        photo = None

    websites = []
    for index in range(MAX_WEBSITES):
        url = forms.safe_url(forms.text(form, f"website_url_{index}", 300))
        label = forms.text(form, f"website_label_{index}", 60)
        if url:
            websites.append({"label": label or url.split("//", 1)[-1].split("/", 1)[0], "url": url})

    email = forms.text(form, "email", 254)
    phone = forms.text(form, "phone", 30)
    save_site_settings(
        session,
        {
            "about": {
                "name": forms.text(form, "name", 80) or "اسم المصمم",
                "title": forms.text(form, "title", 120),
                "bio": forms.text(form, "bio", 2000),
                "photo": photo,
                "phone": phone,
                "whatsapp": _whatsapp_link(phone) if phone else "",
                "email": (forms.email(email) or "") if email else "",
                "location": forms.text(form, "location", 80),
                "skills": forms.text(form, "skills", 300),
                "websites": websites,
            }
        },
    )
    if old_photo and old_photo != photo:
        delete_image(old_photo)
    flash(request, "تم حفظ صفحة «من أنا» ✨")
    return RedirectResponse("/admin/about", status_code=303)
