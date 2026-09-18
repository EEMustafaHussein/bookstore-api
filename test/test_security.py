"""Unit tests: password hashing and tokens."""

from app.security import create_access_token, hash_password, read_user_id_from_token, verify_password


def test_the_same_password_hashes_differently_every_time():
    assert hash_password("reads4ever") != hash_password("reads4ever")


def test_a_hash_verifies_the_right_password_only():
    hashed = hash_password("reads4ever")

    assert verify_password("reads4ever", hashed) is True
    assert verify_password("reads4everr", hashed) is False


def test_a_token_carries_the_user_id_back():
    assert read_user_id_from_token(create_access_token(7)) == 7


def test_a_tampered_token_is_refused():
    assert read_user_id_from_token(create_access_token(7) + "x") is None