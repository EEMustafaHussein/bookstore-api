"""Request DTOs: what a client is ALLOWED to send.
Any field not declared here is thrown away before your code sees it. That is
why none of these has an `id`, a `role` for sign-up, a `user_id` or a price."""

from pydantic import BaseModel, EmailStr, Field, field_validator
from app.enums import OrderStatus, Role


# ----------------------------------------------------------------- users
class UserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def username_is_simple(cls, value):
        if not value.replace("_", "").isalnum():
            raise ValueError("may only contain letters, numbers and underscores")
        return value.lower()

    @field_validator("email")
    @classmethod
    def email_is_lowercase(cls, value):
        return value.lower()

    @field_validator("password")
    @classmethod
    def password_has_letter_and_number(cls, value):
        has_letter = any(char.isalpha() for char in value)
        has_number = any(char.isdigit() for char in value)
        if not (has_letter and has_number):
            raise ValueError("must contain at least one letter and one number")
        return value


class RoleUpdateRequest(BaseModel):
    role: Role


class ActiveUpdateRequest(BaseModel):
    is_active: bool


# --------------------------------------------------------------- authors
class AuthorCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value):
        if not value.strip():
            raise ValueError("cannot be blank")
        return value.strip()


class AuthorProfileRequest(BaseModel):
    bio: str = Field(default="", max_length=2000)
    website: str | None = Field(default=None, max_length=200)


# ---------------------------------------------------------------- genres
class GenreCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)

    @field_validator("name")
    @classmethod
    def name_is_tidy(cls, value):
        if not value.strip():
            raise ValueError("cannot be blank")
        return value.strip().lower()


# ----------------------------------------------------------------- books
class BookCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    author_id: int  # refers to an author that already exists
    genre_ids: list[int] = []  # refer to genres that already exist
    price: float = Field(gt=0)
    stock: int = Field(default=0, ge=0)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value):
        if not value.strip():
            raise ValueError("cannot be blank")
        return value.strip()


class BookUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    author_id: int | None = None
    genre_ids: list[int] | None = None
    price: float | None = Field(default=None, gt=0)
    stock: int | None = Field(default=None, ge=0)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value):
        if value is None:
            return value
        if not value.strip():
            raise ValueError("cannot be blank")
        return value.strip()


# ---------------------------------------------------------------- orders
class OrderCreateRequest(BaseModel):
    book_id: int  # refers to a book that already exists
    quantity: int = Field(default=1, ge=1, le=10)


class OrderStatusUpdateRequest(BaseModel):
    status: OrderStatus


class StockUpdateRequest(BaseModel):
    stock: int = Field(ge=0)