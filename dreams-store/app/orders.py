from datetime import timedelta

from sqlalchemy import update
from sqlmodel import Session, select

from app.cart import Cart
from app.enums import OrderStatus, PaymentMethod, PaymentStatus
from app.models import Order, OrderItem, Product, User, utcnow

# Card orders that stay unpaid longer than this give their reserved stock back.
UNPAID_ORDER_LIFETIME = timedelta(minutes=60)


class CheckoutError(ValueError):
    pass


def place_order(
    session: Session,
    user: User,
    cart: Cart,
    details: dict,
    payment_method: PaymentMethod,
) -> Order:
    if cart.is_empty:
        raise CheckoutError("السلة فارغة")

    needed: dict[int, int] = {}
    for line in cart.lines:
        needed[line.product.id] = needed.get(line.product.id, 0) + line.item.quantity

    # Each product's stock is reduced only if enough is left at this exact moment,
    # so two people can never buy the same last piece.
    for product_id, quantity in needed.items():
        result = session.exec(
            update(Product)
            .where(
                Product.id == product_id,
                Product.stock >= quantity,
                Product.is_published.is_(True),
            )
            .values(stock=Product.stock - quantity)
        )
        if result.rowcount != 1:
            session.rollback()
            name = next(line.product.name for line in cart.lines if line.product.id == product_id)
            raise CheckoutError(f"عذراً، الكمية المطلوبة من «{name}» لم تعد متوفرة")

    awaiting = payment_method == PaymentMethod.card
    order = Order(
        user_id=user.id,
        status=OrderStatus.awaiting_payment if awaiting else OrderStatus.new,
        payment_method=payment_method,
        payment_status=PaymentStatus.unpaid,
        subtotal=cart.subtotal,
        shipping_fee=cart.shipping,
        total=cart.total,
        **details,
    )
    for line in cart.lines:
        order.items.append(
            OrderItem(
                product_id=line.product.id,
                product_name=line.product.name,
                image=line.product.cover,
                unit_price=line.product.price,
                size=line.item.size,
                color=line.item.color,
                quantity=line.item.quantity,
                line_total=line.line_total,
            )
        )
        session.delete(line.item)
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


def restore_stock(session: Session, order: Order) -> None:
    for item in order.items:
        if item.product_id is not None:
            session.exec(
                update(Product)
                .where(Product.id == item.product_id)
                .values(stock=Product.stock + item.quantity)
            )


def cancel_order(session: Session, order: Order) -> None:
    if order.status == OrderStatus.cancelled:
        return
    restore_stock(session, order)
    order.status = OrderStatus.cancelled
    order.updated_at = utcnow()
    session.add(order)
    session.commit()


def mark_paid(session: Session, order: Order, provider: str, reference: str = "") -> None:
    if order.payment_status == PaymentStatus.paid:
        return
    order.payment_status = PaymentStatus.paid
    order.payment_provider = provider
    if reference:
        order.payment_reference = reference
    order.paid_at = utcnow()
    if order.status == OrderStatus.awaiting_payment:
        order.status = OrderStatus.new
    order.updated_at = utcnow()
    session.add(order)
    session.commit()


def stale_unpaid_orders(session: Session) -> list[Order]:
    cutoff = utcnow() - UNPAID_ORDER_LIFETIME
    return list(
        session.exec(
            select(Order).where(
                Order.status == OrderStatus.awaiting_payment, Order.created_at < cutoff
            )
        ).all()
    )
