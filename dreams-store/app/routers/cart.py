from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlmodel import Session

from app import cart as cart_service
from app import forms
from app.cart import MAX_LINE_QUANTITY, Cart, CartError
from app.database import get_session
from app.deps import request_context, wants_json
from app.templating import flash, format_money, media_url, render

router = APIRouter(dependencies=[Depends(request_context)])


def cart_json(cart: Cart, site: dict) -> dict:
    used: dict[int, int] = {}
    for line in cart.lines:
        used[line.product.id] = used.get(line.product.id, 0) + line.item.quantity
    items = []
    for line in cart.lines:
        others = used[line.product.id] - line.item.quantity
        items.append(
            {
                "id": line.item.id,
                "product_id": line.product.id,
                "name": line.product.name,
                "url": f"/product/{line.product.id}",
                "image": media_url(line.product.cover),
                "size": line.item.size,
                "color": line.item.color,
                "quantity": line.item.quantity,
                "max": min(line.product.stock - others, MAX_LINE_QUANTITY),
                "is_bala": line.product.section.value == "bala",
                "unit_text": format_money(line.product.price, site),
                "line_text": format_money(line.line_total, site),
            }
        )
    return {
        "count": cart.count,
        "items": items,
        "subtotal_text": format_money(cart.subtotal, site),
        "shipping_text": format_money(cart.shipping, site) if cart.shipping else "مجاني",
        "total_text": format_money(cart.total, site),
        "remaining_for_free": cart.remaining_for_free_shipping,
        "remaining_text": format_money(cart.remaining_for_free_shipping, site),
        "free_shipping_over": cart.free_shipping_over,
        "progress": (
            min(round(cart.subtotal * 100 / cart.free_shipping_over), 100)
            if cart.free_shipping_over
            else 100
        ),
        "notices": cart.notices,
    }


def _respond(request: Request, session: Session, message: str, ok: bool, back: str):
    if wants_json(request):
        cart = cart_service.load_cart(session, request, request.state.site)
        return JSONResponse(
            {"ok": ok, "message": message, "cart": cart_json(cart, request.state.site)},
            status_code=200 if ok else 400,
        )
    flash(request, message, "success" if ok else "error")
    return RedirectResponse(back, status_code=303)


@router.get("/cart")
def cart_page(request: Request, session: Session = Depends(get_session)):
    cart = cart_service.load_cart(session, request, request.state.site)
    request.state.cart_count = cart.count
    return render(request, "shop/cart.html", {"cart": cart})


@router.get("/api/cart")
def cart_api(request: Request, session: Session = Depends(get_session)):
    cart = cart_service.load_cart(session, request, request.state.site)
    return cart_json(cart, request.state.site)


@router.post("/cart/add")
async def add_to_cart(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    product_raw = forms.text(form, "product_id", 12)
    back = f"/product/{product_raw}" if product_raw.isdigit() else "/shop"
    try:
        quantity = forms.number(form, "quantity") or 1
        cart_service.add_to_cart(
            session,
            request,
            int(product_raw) if product_raw.isdigit() else 0,
            forms.text(form, "size", 40),
            forms.text(form, "color", 40),
            min(quantity, MAX_LINE_QUANTITY),
        )
    except ValueError as exc:
        message = str(exc) if isinstance(exc, CartError) else "الكمية غير صحيحة"
        return _respond(request, session, message, False, back)
    return _respond(request, session, "أُضيفت القطعة إلى سلتكِ 🛍️", True, back)


@router.post("/cart/items/{item_id}")
async def update_item(item_id: int, request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    try:
        quantity = forms.number(form, "quantity")
        if quantity is None:
            raise CartError("الكمية غير صحيحة")
        cart_service.set_quantity(session, request, item_id, quantity)
    except ValueError as exc:
        message = str(exc) if isinstance(exc, CartError) else "الكمية غير صحيحة"
        return _respond(request, session, message, False, "/cart")
    return _respond(request, session, "تم تحديث السلة", True, "/cart")


@router.post("/cart/items/{item_id}/remove")
def remove_item(item_id: int, request: Request, session: Session = Depends(get_session)):
    try:
        cart_service.remove_item(session, request, item_id)
    except CartError as exc:
        return _respond(request, session, str(exc), False, "/cart")
    return _respond(request, session, "تمت إزالة القطعة من السلة", True, "/cart")
