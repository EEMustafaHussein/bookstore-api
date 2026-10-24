from dataclasses import dataclass, field

from fastapi import Request
from sqlalchemy import func
from sqlmodel import Session, select

from app.database import get_by_id
from app.models import CartItem, Product
from app.security import new_token

MAX_LINE_QUANTITY = 20


class CartError(ValueError):
    pass


@dataclass
class CartLine:
    item: CartItem
    product: Product

    @property
    def line_total(self) -> int:
        return self.product.price * self.item.quantity


@dataclass
class Cart:
    lines: list[CartLine] = field(default_factory=list)
    subtotal: int = 0
    shipping: int = 0
    total: int = 0
    count: int = 0
    free_shipping_over: int = 0
    # Lines that were dropped or reduced because stock changed since they were added.
    notices: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.lines

    @property
    def remaining_for_free_shipping(self) -> int:
        if not self.free_shipping_over or self.is_empty:
            return 0
        return max(self.free_shipping_over - self.subtotal, 0)


def shipping_for(subtotal: int, site: dict) -> int:
    if subtotal <= 0:
        return 0
    free_over = int(site.get("free_shipping_over") or 0)
    if free_over and subtotal >= free_over:
        return 0
    return int(site.get("shipping_fee") or 0)


def _owner_filter(request: Request, create: bool = False):
    user = getattr(request.state, "user", None)
    if user is not None:
        return CartItem.user_id == user.id, {"user_id": user.id}
    token = request.session.get("cart_token")
    if token is None:
        if not create:
            return None, {}
        token = new_token()
        request.session["cart_token"] = token
    return (CartItem.user_id.is_(None)) & (CartItem.cart_token == token), {"cart_token": token}


def _items(session: Session, condition) -> list[CartItem]:
    return list(session.exec(select(CartItem).where(condition).order_by(CartItem.id)).all())


def cart_count(session: Session, request: Request) -> int:
    condition, _ = _owner_filter(request)
    if condition is None:
        return 0
    total = session.exec(select(func.sum(CartItem.quantity)).where(condition)).one()
    return int(total or 0)


def load_cart(session: Session, request: Request, site: dict) -> Cart:
    cart = Cart(free_shipping_over=int(site.get("free_shipping_over") or 0))
    condition, _ = _owner_filter(request)
    if condition is None:
        return cart

    changed = False
    used: dict[int, int] = {}
    for item in _items(session, condition):
        product = item.product
        if product is None or not product.is_published or product.stock <= 0:
            if product is not None:
                cart.notices.append(f"«{product.name}» لم يعد متوفراً وتمت إزالته من السلة")
            session.delete(item)
            changed = True
            continue
        available = product.stock - used.get(product.id, 0)
        if available <= 0:
            session.delete(item)
            changed = True
            cart.notices.append(f"تم تعديل كمية «{product.name}» حسب المتوفر")
            continue
        if item.quantity > available:
            item.quantity = available
            session.add(item)
            changed = True
            cart.notices.append(f"تم تعديل كمية «{product.name}» حسب المتوفر")
        used[product.id] = used.get(product.id, 0) + item.quantity
        cart.lines.append(CartLine(item=item, product=product))

    if changed:
        session.commit()
        for line in cart.lines:
            session.refresh(line.item)

    cart.subtotal = sum(line.line_total for line in cart.lines)
    cart.count = sum(line.item.quantity for line in cart.lines)
    cart.shipping = shipping_for(cart.subtotal, site)
    cart.total = cart.subtotal + cart.shipping
    return cart


def _quantity_in_cart(items: list[CartItem], product_id: int, skip_id: int | None = None) -> int:
    return sum(
        item.quantity for item in items if item.product_id == product_id and item.id != skip_id
    )


def add_to_cart(
    session: Session,
    request: Request,
    product_id: int,
    size: str,
    color: str,
    quantity: int,
) -> CartItem:
    product = get_by_id(session, Product, product_id)
    if product is None or not product.is_published:
        raise CartError("هذا المنتج غير متوفر")
    if product.stock <= 0:
        raise CartError("نفدت الكمية من هذا المنتج")
    if quantity < 1:
        raise CartError("الكمية غير صحيحة")

    size, color = size.strip(), color.strip()
    if product.size_list:
        if size not in product.size_list:
            raise CartError("اختاري المقاس أولاً")
    else:
        size = ""
    if product.color_list:
        if color not in product.color_list:
            raise CartError("اختاري اللون أولاً")
    else:
        color = ""

    condition, owner = _owner_filter(request, create=True)
    items = _items(session, condition)
    already = _quantity_in_cart(items, product.id)
    if already + quantity > product.stock:
        left = product.stock - already
        if left <= 0:
            raise CartError("أضفتِ كل الكمية المتوفرة من هذا المنتج إلى السلة")
        raise CartError(f"المتوفر من هذا المنتج {product.stock} فقط")

    line = next(
        (i for i in items if i.product_id == product.id and i.size == size and i.color == color),
        None,
    )
    if line is None:
        line = CartItem(product_id=product.id, size=size, color=color, quantity=0, **owner)
    if line.quantity + quantity > MAX_LINE_QUANTITY:
        raise CartError(f"الحد الأقصى {MAX_LINE_QUANTITY} قطعة لكل منتج")
    line.quantity += quantity
    session.add(line)
    session.commit()
    session.refresh(line)
    return line


def _own_item(session: Session, request: Request, item_id: int) -> tuple[CartItem, list[CartItem]]:
    condition, _ = _owner_filter(request)
    if condition is None:
        raise CartError("السلة فارغة")
    items = _items(session, condition)
    item = next((i for i in items if i.id == item_id), None)
    if item is None:
        raise CartError("هذه القطعة لم تعد في السلة")
    return item, items


def set_quantity(session: Session, request: Request, item_id: int, quantity: int) -> None:
    item, items = _own_item(session, request, item_id)
    if quantity <= 0:
        session.delete(item)
        session.commit()
        return
    available = item.product.stock - _quantity_in_cart(items, item.product_id, skip_id=item.id)
    if quantity > available:
        raise CartError(f"المتوفر من هذا المنتج {max(item.product.stock, 0)} فقط")
    if quantity > MAX_LINE_QUANTITY:
        raise CartError(f"الحد الأقصى {MAX_LINE_QUANTITY} قطعة لكل منتج")
    item.quantity = quantity
    session.add(item)
    session.commit()


def remove_item(session: Session, request: Request, item_id: int) -> None:
    item, _ = _own_item(session, request, item_id)
    session.delete(item)
    session.commit()


def merge_guest_cart(session: Session, token: str | None, user_id: int) -> None:
    """Moves what a visitor added before signing in into their account's cart."""
    if not token:
        return
    guest_items = _items(session, (CartItem.user_id.is_(None)) & (CartItem.cart_token == token))
    if not guest_items:
        return
    user_items = _items(session, CartItem.user_id == user_id)
    for guest in guest_items:
        match = next(
            (
                i
                for i in user_items
                if i.product_id == guest.product_id and i.size == guest.size and i.color == guest.color
            ),
            None,
        )
        if match is None:
            guest.user_id = user_id
            guest.cart_token = None
            session.add(guest)
            user_items.append(guest)
        else:
            match.quantity = min(match.quantity + guest.quantity, MAX_LINE_QUANTITY)
            session.add(match)
            session.delete(guest)
    # Quantities are trimmed to the stock left the next time the cart is loaded.
    session.commit()


def clear_cart(session: Session, request: Request) -> None:
    condition, _ = _owner_filter(request)
    if condition is None:
        return
    for item in _items(session, condition):
        session.delete(item)
