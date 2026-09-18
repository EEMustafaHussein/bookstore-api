"""Integration tests: buying books, and seeing only your own orders."""


def test_placing_an_order_takes_the_books_off_the_shelf(client, customer, a_book):
    response = client.post("/orders", json={"book_id": a_book["id"], "quantity": 2}, headers=customer)

    assert response.status_code == 201
    assert response.json()["total_price"] == 25.0
    assert client.get(f"/books/{a_book['id']}").json()["stock"] == 1


def test_ordering_more_than_the_shop_has_is_refused(client, customer, a_book):
    response = client.post("/orders", json={"book_id": a_book["id"], "quantity": 5}, headers=customer)

    assert response.status_code == 409
    assert client.get(f"/books/{a_book['id']}").json()["stock"] == 3


def test_an_order_belongs_to_whoever_the_token_says(client, session, customer, staff, a_book):
    other_user_id = 999

    response = client.post(
        "/orders",
        json={"book_id": a_book["id"], "quantity": 1, "user_id": other_user_id},
        headers=customer,
    )

    assert response.json()["user_id"] != other_user_id


def test_ordering_a_book_that_does_not_exist_gives_404(client, customer):
    assert client.post("/orders", json={"book_id": 999}, headers=customer).status_code == 404


def test_a_customer_sees_only_their_own_orders(client, customer, staff, a_book):
    client.post("/orders", json={"book_id": a_book["id"], "quantity": 1}, headers=customer)
    client.post("/orders", json={"book_id": a_book["id"], "quantity": 1}, headers=staff)

    assert len(client.get("/orders", headers=customer).json()) == 1
    assert len(client.get("/orders", headers=staff).json()) == 2


def test_someone_elses_order_looks_like_it_does_not_exist(client, customer, staff, a_book):
    order = client.post("/orders", json={"book_id": a_book["id"], "quantity": 1}, headers=staff).json()

    assert client.get(f"/orders/{order['id']}", headers=customer).status_code == 404


def test_only_staff_can_change_an_order_status(client, customer, staff, a_book):
    order = client.post("/orders", json={"book_id": a_book["id"], "quantity": 1}, headers=customer).json()

    assert client.patch(f"/orders/{order['id']}/status", json={"status": "shipped"}, headers=customer).status_code == 403
    assert client.patch(f"/orders/{order['id']}/status", json={"status": "shipped"}, headers=staff).status_code == 200


def test_cancelling_puts_the_books_back(client, customer, staff, a_book):
    order = client.post("/orders", json={"book_id": a_book["id"], "quantity": 2}, headers=customer).json()

    client.patch(f"/orders/{order['id']}/status", json={"status": "cancelled"}, headers=staff)

    assert client.get(f"/books/{a_book['id']}").json()["stock"] == 3