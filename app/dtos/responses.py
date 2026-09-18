"""Response DTOs: what a client is ALLOWED to see.
Routes use these as their response_model, so anything not declared here --
like a password hash -- is stripped out before the response leaves."""

from datetime import datetime
from pydantic import BaseModel
from app.enums import OrderStatus, Role


# ----------------------------------------------------------------- users
class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: Role
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --------------------------------------------------------------- authors
class AuthorSummaryResponse(BaseModel):
    """An author as it appears inside a book: no list of books."""

    id: int
    name: str


class BookSummaryResponse(BaseModel):
    """A book as it appears inside an author: no author inside it."""

    id: int
    title: str


class AuthorProfileResponse(BaseModel):
    bio: str
    website: str | None


class AuthorResponse(BaseModel):
    id: int
    name: str
    email: str | None
    profile: AuthorProfileResponse | None
    books: list[BookSummaryResponse]


class AuthorListItemResponse(BaseModel):
    id: int
    name: str
    book_count: int


# ---------------------------------------------------------------- genres
class GenreResponse(BaseModel):
    id: int
    name: str


# ----------------------------------------------------------------- books
class BookResponse(BaseModel):
    id: int
    title: str
    price: float
    stock: int
    author: AuthorSummaryResponse
    genres: list[GenreResponse]


# ---------------------------------------------------------------- orders
class OrderResponse(BaseModel):
    id: int
    user_id: int
    book_id: int
    quantity: int
    total_price: float
    status: OrderStatus
    created_at: datetime