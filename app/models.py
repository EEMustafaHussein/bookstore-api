from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Field, Relationship, SQLModel
from app.enums import OrderStatus, Role


class User(SQLModel, table=True):
    __table_args__ = {"sqlite_autoincrement": True}

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    role: Role = Role.customer
    is_active: bool = True


class Author(SQLModel, table=True):
    __table_args__ = {"sqlite_autoincrement": True}

    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str | None = None

    books: list["Book"] = Relationship(back_populates="author")
    profile: Optional["AuthorProfile"] = Relationship(
        back_populates="author",
        sa_relationship_kwargs={"uselist": False, "cascade": "all, delete-orphan"},
    )


class AuthorProfile(SQLModel, table=True):
    __tablename__ = "author_profile"

    author_id: int = Field(foreign_key="author.id", primary_key=True)
    bio: str = ""
    website: str | None = None

    author: Author = Relationship(back_populates="profile")


class BookGenreLink(SQLModel, table=True):
    __tablename__ = "book_genre"

    book_id: int = Field(foreign_key="book.id", primary_key=True)
    genre_id: int = Field(foreign_key="genre.id", primary_key=True, index=True)


class Genre(SQLModel, table=True):
    __table_args__ = {"sqlite_autoincrement": True}

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)

    books: list["Book"] = Relationship(back_populates="genres", link_model=BookGenreLink)


class Book(SQLModel, table=True):
    __table_args__ = {"sqlite_autoincrement": True}

    id: int | None = Field(default=None, primary_key=True)
    title: str
    author_id: int = Field(foreign_key="author.id", index=True)
    price: float
    stock: int = 0

    author: Author = Relationship(back_populates="books")
    genres: list[Genre] = Relationship(back_populates="books", link_model=BookGenreLink)


class Order(SQLModel, table=True):
    __table_args__ = {"sqlite_autoincrement": True}

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    book_id: int = Field(foreign_key="book.id", index=True)
    quantity: int
    total_price: float
    status: OrderStatus = OrderStatus.pending
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))