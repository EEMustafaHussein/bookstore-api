from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlmodel import Session, select

from app import cart as cart_service
from app import forms
from app.config import settings
from app.database import get_by_id, get_session
from app.deps import current_user, request_context
from app.enums import GOVERNORATES, OrderStatus, PaymentMethod, PaymentStatus
from app.models import Order, User
from app.orders import CheckoutError, cancel_order, mark_paid, place_order
from app.payments import release_stale_orders, stripe
from app.templating import flash, render

router = APIRouter(dependencies=[Depends(request_context)])
webhook_router = APIRouter()


def own_order(session: Session, user: User, order_id: int | str | None) -> Order:
    order = get_by_id(session, Order, order_id)
    if order is None or order.user_id != user.id:
        raise HTTPException(status_code=404, detail="هذا الطلب غير موجود")
    return order


def _order_page(order: Order, placed: bool = False) -> RedirectResponse:
    suffix = "?placed=1" if placed else ""
    return RedirectResponse(f"/account/orders/{order.id}{suffix}", status_code=303)


def _payment_methods() -> list[PaymentMethod]:
    methods = [PaymentMethod.cod]
    if settings.card_payments_enabled:
        methods.append(PaymentMethod.card)
    return methods


def _checkout_page(request, cart, values, errors, status_code=200):
    return render(
        request,
        "shop/checkout.html",
        {
            "cart": cart,
            "values": values,
            "errors": errors,
            "payment_methods": _payment_methods(),
        },
        status_code=status_code,
    )


@router.get("/checkout")
def checkout_page(
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    cart = cart_service.load_cart(session, request, request.state.site)
    if cart.is_empty:
        flash(request, "سلتكِ فارغة، أضيفي بعض القطع أولاً", "info")
        return RedirectResponse("/cart", status_code=303)

    last = session.exec(
        select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc())
    ).first()
    values = {
        "full_name": last.full_name if last else user.name,
        "phone": last.phone if last else user.phone,
        "governorate": last.governorate if last else "بغداد",
        "city": last.city if last else "",
        "address": last.address if last else "",
        "notes": "",
        "payment_method": PaymentMethod.cod.value,
    }
    errors = {"cart": "تغيّرت بعض القطع في سلتكِ: " + " — ".join(cart.notices)} if cart.notices else {}
    return _checkout_page(request, cart, values, errors)


@router.post("/checkout")
async def checkout(
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    form = await request.form()
    values = {
        "full_name": forms.text(form, "full_name", 80),
        "phone": forms.text(form, "phone", 20),
        "governorate": forms.text(form, "governorate", 40),
        "city": forms.text(form, "city", 80),
        "address": forms.text(form, "address", 300),
        "notes": forms.text(form, "notes", 500),
        "payment_method": forms.text(form, "payment_method", 10),
    }
    errors = {}
    if len(values["full_name"]) < 3:
        errors["full_name"] = "اكتبي الاسم الكامل"
    phone = forms.iraqi_mobile(values["phone"])
    if phone is None:
        errors["phone"] = "رقم الهاتف غير صحيح، مثال: 07701234567"
    if values["governorate"] not in GOVERNORATES:
        errors["governorate"] = "اختاري المحافظة"
    if len(values["city"]) < 2:
        errors["city"] = "اكتبي المدينة أو المنطقة"
    if len(values["address"]) < 5:
        errors["address"] = "اكتبي العنوان بالتفصيل (الحي، الشارع، أقرب نقطة دالة)"
    allowed = {method.value for method in _payment_methods()}
    if values["payment_method"] not in allowed:
        errors["payment_method"] = "اختاري طريقة الدفع"

    release_stale_orders(session)
    cart = cart_service.load_cart(session, request, request.state.site)
    if cart.is_empty:
        flash(request, "سلتكِ فارغة، أضيفي بعض القطع أولاً", "info")
        return RedirectResponse("/cart", status_code=303)
    if cart.notices:
        errors["cart"] = "تغيّرت بعض القطع في سلتكِ: " + " — ".join(cart.notices)
    if errors:
        return _checkout_page(request, cart, values, errors, status_code=400)

    method = PaymentMethod(values["payment_method"])
    details = {key: values[key] for key in ("full_name", "governorate", "city", "address", "notes")}
    details["phone"] = phone
    try:
        order = place_order(session, user, cart, details, method)
    except CheckoutError as exc:
        flash(request, str(exc), "error")
        return RedirectResponse("/cart", status_code=303)

    request.state.cart_count = 0
    if method == PaymentMethod.card:
        return RedirectResponse(f"/checkout/pay/{order.id}", status_code=303)
    flash(request, "تم استلام طلبكِ بنجاح 🎉 سنتواصل معكِ لتأكيده")
    return _order_page(order, placed=True)


@router.get("/checkout/pay/{order_id}")
def pay(
    order_id: int,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    order = own_order(session, user, order_id)
    if order.status != OrderStatus.awaiting_payment:
        return _order_page(order)

    if settings.stripe_enabled:
        try:
            checkout_session = stripe.create_checkout_session(
                order, user.email, request.state.site["site_name"]
            )
        except stripe.PaymentError as exc:
            flash(request, f"تعذّر فتح صفحة الدفع: {exc}", "error")
            return _order_page(order)
        order.payment_provider = "stripe"
        order.payment_reference = checkout_session["id"]
        session.add(order)
        session.commit()
        return RedirectResponse(checkout_session["url"], status_code=303)

    if settings.payment_demo_mode:
        return render(request, "shop/demo_pay.html", {"order": order})

    flash(request, "الدفع بالبطاقة غير متاح حالياً", "error")
    return _order_page(order)


@router.post("/checkout/demo/{order_id}")
async def demo_payment(
    order_id: int,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    if not settings.payment_demo_mode or settings.stripe_enabled:
        raise HTTPException(status_code=404, detail="الصفحة غير موجودة")
    order = own_order(session, user, order_id)
    form = await request.form()
    if order.status != OrderStatus.awaiting_payment:
        return _order_page(order)
    if form.get("action") == "pay":
        mark_paid(session, order, "demo", f"demo-{order.id}")
        flash(request, "تم الدفع بنجاح (وضع تجريبي) 🎉")
        return _order_page(order, placed=True)
    flash(request, "لم تكتمل عملية الدفع، يمكنكِ المحاولة مجدداً من صفحة الطلب", "info")
    return _order_page(order)


@router.get("/checkout/success")
def payment_success(
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    order = own_order(session, user, request.query_params.get("order"))
    session_id = request.query_params.get("session_id", "")
    if order.payment_status == PaymentStatus.paid:
        return _order_page(order, placed=True)
    if not settings.stripe_enabled or not session_id:
        return _order_page(order)
    try:
        checkout_session = stripe.retrieve_checkout_session(session_id)
    except stripe.PaymentError:
        flash(request, "لم نتمكن من التحقق من الدفع الآن، سيتم تحديث الطلب تلقائياً", "info")
        return _order_page(order)
    if stripe.session_is_paid(checkout_session, order):
        mark_paid(session, order, "stripe", checkout_session.get("id", ""))
        flash(request, "تم الدفع بنجاح 🎉 شكراً لكِ")
        return _order_page(order, placed=True)
    flash(request, "لم يكتمل الدفع بعد", "info")
    return _order_page(order)


@router.get("/checkout/cancel")
def payment_cancelled(
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    order = own_order(session, user, request.query_params.get("order"))
    flash(request, "تم إلغاء عملية الدفع، يمكنكِ المحاولة مجدداً من صفحة الطلب", "info")
    return _order_page(order)


@webhook_router.post("/checkout/stripe/webhook")
async def stripe_webhook(request: Request, session: Session = Depends(get_session)):
    payload = await request.body()
    try:
        event = stripe.parse_webhook(payload, request.headers.get("stripe-signature"))
    except stripe.PaymentError:
        return JSONResponse({"error": "invalid signature"}, status_code=400)

    obj = event.get("data", {}).get("object", {}) or {}
    reference = obj.get("client_reference_id") or (obj.get("metadata") or {}).get("order_id")
    order = get_by_id(session, Order, str(reference)) if reference else None
    if order is None:
        return {"received": True}

    kind = event.get("type")
    if kind in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        if stripe.session_is_paid(obj, order):
            mark_paid(session, order, "stripe", obj.get("id", ""))
    elif kind == "checkout.session.expired":
        if order.status == OrderStatus.awaiting_payment and order.payment_reference == obj.get("id"):
            cancel_order(session, order)
    return {"received": True}
