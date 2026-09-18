"""Integration tests: signing up, logging in, and who am I."""

SIGNUP = {"username": "amina", "email": "amina@example.com", "password": "reads4ever"}


def test_signup_returns_a_customer_without_the_password(client):
    response = client.post("/auth/register", json=SIGNUP)

    assert response.status_code == 201
    assert response.json()["role"] == "customer"
    assert "hashed_password" not in response.json()
    assert "password" not in response.json()


def test_signup_cannot_make_an_admin(client):
    response = client.post("/auth/register", json={**SIGNUP, "role": "admin"})

    assert response.json()["role"] == "customer"


def test_the_same_username_cannot_be_taken_twice(client):
    client.post("/auth/register", json=SIGNUP)

    response = client.post("/auth/register", json={**SIGNUP, "email": "other@example.com"})

    assert response.status_code == 409


def test_login_returns_a_token(client):
    client.post("/auth/register", json=SIGNUP)

    response = client.post("/auth/login", data={"username": "amina", "password": "reads4ever"})

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"


def test_a_wrong_password_and_an_unknown_user_look_identical(client):
    client.post("/auth/register", json=SIGNUP)

    wrong_password = client.post("/auth/login", data={"username": "amina", "password": "wrongpass1"})
    no_such_user = client.post("/auth/login", data={"username": "ghost", "password": "wrongpass1"})

    assert wrong_password.status_code == no_such_user.status_code == 401
    assert wrong_password.json() == no_such_user.json()


def test_me_needs_a_token(client):
    assert client.get("/auth/me").status_code == 401


def test_me_reports_the_logged_in_user(client, customer):
    response = client.get("/auth/me", headers=customer)

    assert response.status_code == 200
    assert response.json()["username"] == "amina"