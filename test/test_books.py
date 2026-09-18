"""Integration tests: the catalogue, and who is allowed to change it."""

NEW_BOOK = {"title": "Dune", "author": "Frank Herbert", "genre": "fiction", "price": 12.5, "stock": 3}


def test_anyone_can_list_books_and_it_starts_empty(client):
    response = client.get("/books")

    assert response.status_code == 200
    assert response.json() == []


def test_staff_can_add_a_book_and_the_database_gives_it_an_id(client, staff):
    response = client.post("/books", json=NEW_BOOK, headers=staff)

    assert response.status_code == 201
    assert response.json()["id"] is not None
    assert response.json()["title"] == "Dune"


def test_a_new_book_appears_in_the_list(client, staff):
    client.post("/books", json=NEW_BOOK, headers=staff)

    titles = [book["title"] for book in client.get("/books").json()]

    assert titles == ["Dune"]


def test_a_visitor_who_is_not_logged_in_cannot_add_a_book(client):
    assert client.post("/books", json=NEW_BOOK).status_code == 401


def test_a_customer_cannot_add_a_book(client, customer):
    assert client.post("/books", json=NEW_BOOK, headers=customer).status_code == 403


def test_a_blank_title_is_refused(client, staff):
    response = client.post("/books", json={**NEW_BOOK, "title": "   "}, headers=staff)

    assert response.status_code == 422


def test_a_client_cannot_choose_the_id(client, staff):
    response = client.post("/books", json={**NEW_BOOK, "id": 99}, headers=staff)

    assert response.json()["id"] != 99


def test_asking_for_a_book_that_does_not_exist_gives_404(client):
    assert client.get("/books/999").status_code == 404


def test_staff_can_change_only_the_price(client, staff, a_book):
    response = client.patch(f"/books/{a_book['id']}", json={"price": 11.0}, headers=staff)

    assert response.status_code == 200
    assert response.json()["price"] == 11.0
    assert response.json()["title"] == "Dune"


def test_only_an_admin_can_delete_a_book(client, staff, admin, a_book):
    assert client.delete(f"/books/{a_book['id']}", headers=staff).status_code == 403
    assert client.delete(f"/books/{a_book['id']}", headers=admin).status_code == 204
    assert client.get(f"/books/{a_book['id']}").status_code == 404