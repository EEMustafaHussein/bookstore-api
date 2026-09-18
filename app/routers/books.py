from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.database import get_session
from app.dependencies import require_roles
from app.dtos.requests import BookCreateRequest, BookUpdateRequest, StockUpdateRequest
from app.dtos.responses import BookResponse
from app.enums import Role
from app.models import Author, Book, Genre, User

router = APIRouter(prefix="/books", tags=["books"])

staff_or_admin = require_roles([Role.staff, Role.admin])
admin_only = require_roles([Role.admin])


def get_book_or_404(session: Session, book_id: int) -> Book:
    book = session.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


@router.get("", response_model=list[BookResponse])
def list_books(
    genre_id: int | None = None,
    author_id: int | None = None,
    session: Session = Depends(get_session),
):
    query = select(Book)
    if genre_id is not None:
        query = query.join(Book.genres).where(Genre.id == genre_id)
    if author_id is not None:
        query = query.where(Book.author_id == author_id)
    query = query.order_by(Book.id)
    return session.exec(query).all()


@router.get("/{book_id}", response_model=BookResponse)
def get_book(book_id: int, session: Session = Depends(get_session)):
    return get_book_or_404(session, book_id)


@router.post("", response_model=BookResponse, status_code=201)
def create_book(
    new_book: BookCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(staff_or_admin),
):
    # Verify author exists
    if session.get(Author, new_book.author_id) is None:
        raise HTTPException(status_code=404, detail="Author not found")

    # Verify all genres exist
    genres = []
    if new_book.genre_ids:
        genres = session.exec(
            select(Genre).where(Genre.id.in_(new_book.genre_ids))
        ).all()
        if len(genres) != len(new_book.genre_ids):
            raise HTTPException(
                status_code=404, detail="One or more genres not found"
            )

    book = Book(
        title=new_book.title,
        author_id=new_book.author_id,
        price=new_book.price,
        stock=new_book.stock,
        genres=genres,
    )
    session.add(book)
    session.commit()
    session.refresh(book)
    return book


@router.put("/{book_id}", response_model=BookResponse)
def update_book(
    book_id: int,
    book_update: BookUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(staff_or_admin),
):
    book = get_book_or_404(session, book_id)

    if book_update.author_id is not None:
        if session.get(Author, book_update.author_id) is None:
            raise HTTPException(status_code=404, detail="Author not found")
        book.author_id = book_update.author_id

    if book_update.genre_ids is not None:
        genres = session.exec(
            select(Genre).where(Genre.id.in_(book_update.genre_ids))
        ).all()
        if len(genres) != len(book_update.genre_ids):
            raise HTTPException(
                status_code=404, detail="One or more genres not found"
            )
        book.genres = genres

    if book_update.title is not None:
        book.title = book_update.title
    if book_update.price is not None:
        book.price = book_update.price
    if book_update.stock is not None:
        book.stock = book_update.stock

    session.add(book)
    session.commit()
    session.refresh(book)
    return book


@router.patch("/{book_id}/stock", response_model=BookResponse)
def update_book_stock(
    book_id: int,
    stock_in: StockUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(staff_or_admin),
):
    book = get_book_or_404(session, book_id)
    book.stock = stock_in.stock
    session.add(book)
    session.commit()
    session.refresh(book)
    return book


@router.delete("/{book_id}", status_code=204)
def delete_book(
    book_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(admin_only),
):
    book = get_book_or_404(session, book_id)
    session.delete(book)
    session.commit()