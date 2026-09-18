from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.database import get_session
from app.dependencies import get_current_user
from app.dtos.requests import OrderCreateRequest
from app.dtos.responses import OrderResponse
from app.enums import OrderStatus, Role
from app.models import Book, Order, User

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
        order_in: OrderCreateRequest,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
):
    book = session.get(Book, order_in.book_id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found",
        )

    if book.stock < order_in.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not enough stock available",
        )

    book.stock -= order_in.quantity
    total_price = book.price * order_in.quantity

    order = Order(
        user_id=current_user.id,
        book_id=book.id,
        quantity=order_in.quantity,
        total_price=total_price,
        status=OrderStatus.pending,
    )

    session.add(book)
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


@router.get("/", response_model=list[OrderResponse])
def get_orders(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
):
    if current_user.role in [Role.admin, Role.staff]:
        orders = session.exec(select(Order)).all()
    else:
        orders = session.exec(select(Order).where(Order.user_id == current_user.id)).all()
    return orders


@router.patch("/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(
        order_id: int,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    if current_user.role not in [Role.admin, Role.staff] and order.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough privileges",
        )

    if order.status == OrderStatus.cancelled:
        return order

    if order.status != OrderStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only cancel pending orders",
        )

    book = session.get(Book, order.book_id)
    if book:
        book.stock += order.quantity
        session.add(book)

    order.status = OrderStatus.cancelled
    session.add(order)
    session.commit()
    session.refresh(order)
    return order