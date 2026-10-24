from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app import forms
from app.database import get_session
from app.deps import current_user, request_context
from app.models import Order, User
from app.orders import cancel_order
from app.payments import release_stale_orders
from app.routers.checkout import own_order
from app.security import hash_password, password_problem, verify_password
from app.templating import flash, render

router = APIRouter(prefix="/account", dependencies=[Depends(request_context)])


@router.get("")
def account(
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    release_stale_orders(session)
    orders = session.exec(
        select(Order)
        .where(Order.user_id == user.id)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
    ).all()
    return render(request, "account/index.html", {"orders": orders})


@router.get("/orders/{order_id}")
def order_detail(
    order_id: int,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    order = own_order(session, user, order_id)
    placed = request.query_params.get("placed") == "1"
    return render(request, "account/order.html", {"order": order, "placed": placed})


@router.post("/orders/{order_id}/cancel")
def cancel(
    order_id: int,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    order = own_order(session, user, order_id)
    if order.can_be_cancelled_by_customer:
        cancel_order(session, order)
        flash(request, "تم إلغاء الطلب")
    else:
        flash(request, "لا يمكن إلغاء هذا الطلب الآن، تواصلي معنا للمساعدة", "error")
    return RedirectResponse(f"/account/orders/{order.id}", status_code=303)


@router.post("/profile")
async def update_profile(
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    form = await request.form()
    name = forms.text(form, "name", 80)
    phone_raw = forms.text(form, "phone", 20)
    phone = forms.iraqi_mobile(phone_raw) if phone_raw else ""
    if len(name) < 2:
        flash(request, "اكتبي اسمكِ", "error")
    elif phone is None:
        flash(request, "رقم الهاتف غير صحيح، مثال: 07701234567", "error")
    else:
        user.name = name
        user.phone = phone
        session.add(user)
        session.commit()
        flash(request, "تم حفظ بياناتكِ")
    return RedirectResponse("/account#profile", status_code=303)


@router.post("/password")
async def change_password(
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    form = await request.form()
    current = forms.secret(form, "current_password")
    new = forms.secret(form, "new_password")
    confirm = forms.secret(form, "new_password_confirm")
    problem = password_problem(new)
    if not verify_password(current, user.hashed_password):
        flash(request, "كلمة المرور الحالية غير صحيحة", "error")
    elif problem:
        flash(request, problem, "error")
    elif new != confirm:
        flash(request, "كلمتا المرور الجديدتان غير متطابقتين", "error")
    else:
        user.hashed_password = hash_password(new)
        session.add(user)
        session.commit()
        flash(request, "تم تغيير كلمة المرور")
    return RedirectResponse("/account#security", status_code=303)
