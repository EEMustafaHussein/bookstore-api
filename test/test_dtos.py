"""Unit tests: the DTO validators, with no database and no HTTP."""

import pytest
from pydantic import ValidationError

from app.dtos.requests import BookCreateRequest, UserCreateRequest


@pytest.fixture(name="book_fields")
def book_fields_fixture():
    """Valid values for everything except the field under test."""
    return {"author": "Frank Herbert", "genre": "fiction", "price": 12.5}


def test_valid_book_is_accepted(book_fields):
    book = BookCreateRequest(title="Dune", **book_fields)

    assert book.title == "Dune"
    assert book.stock == 0  # the default


def test_title_is_trimmed(book_fields):
    assert BookCreateRequest(title="  Dune  ", **book_fields).title == "Dune"


@pytest.mark.parametrize("title", ["", "   ", "\t"])
def test_blank_titles_are_rejected(title, book_fields):
    with pytest.raises(ValidationError):
        BookCreateRequest(title=title, **book_fields)


def test_unknown_genre_is_rejected(book_fields):
    with pytest.raises(ValidationError):
        BookCreateRequest(title="Dune", **{**book_fields, "genre": "comedy"})


@pytest.mark.parametrize("price", [0, -1])
def test_price_must_be_positive(price, book_fields):
    with pytest.raises(ValidationError):
        BookCreateRequest(title="Dune", **{**book_fields, "price": price})


def test_signup_lowercases_username_and_email():
    user = UserCreateRequest(username="Amina", email="Amina@Example.com", password="reads4ever")

    assert user.username == "amina"
    assert user.email == "amina@example.com"


def test_signup_ignores_a_role_the_client_tries_to_set():
    user = UserCreateRequest(
        username="sneaky", email="s@example.com", password="letmein99", role="admin"
    )

    assert not hasattr(user, "role")


@pytest.mark.parametrize("password", ["short1", "nodigitshere", "12345678"])
def test_weak_passwords_are_rejected(password):
    with pytest.raises(ValidationError):
        UserCreateRequest(username="amina", email="a@example.com", password=password)