"""Integration tests for the tables added in DATABASE.md."""


def test_a_new_author_has_no_books_and_no_profile(client, staff):
    response = client.post("/authors", json={"name": "Frank Herbert"}, headers=staff)

    assert response.status_code == 201
    assert response.json()["books"] == []
    assert response.json()["profile"] is None


def test_a_book_shows_its_author_and_genres_nested(client, staff):
    author = client.post("/authors", json={"name": "Frank Herbert"}, headers=staff).json()
    fiction = client.post("/genres", json={"name": "fiction"}, headers=staff).json()
    classic = client.post("/genres", json={"name": "classic"}, headers=staff).json()

    book = client.post(
        "/books",
        json={"title": "Dune", "author_id": author["id"],
              "genre_ids": [fiction["id"], classic["id"]], "price": 12.5, "stock": 3},
        headers=staff,
    ).json()

    assert book["author"] == {"id": author["id"], "name": "Frank Herbert"}
    assert sorted(genre["name"] for genre in book["genres"]) == ["classic", "fiction"]


def test_a_book_for_an_author_who_does_not_exist_is_refused(client, staff):
    response = client.post(
        "/books",
        json={"title": "Ghost", "author_id": 999, "price": 1.0},
        headers=staff,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Author not found"


def test_the_author_list_counts_books_and_keeps_authors_with_none(client, staff):
    herbert = client.post("/authors", json={"name": "Frank Herbert"}, headers=staff).json()
    client.post("/authors", json={"name": "Jane Austen"}, headers=staff)
    client.post("/books", json={"title": "Dune", "author_id": herbert["id"], "price": 12.5}, headers=staff)

    counts = {author["name"]: author["book_count"] for author in client.get("/authors").json()}

    assert counts == {"Frank Herbert": 1, "Jane Austen": 0}          # LEFT JOIN
    assert [a["name"] for a in client.get("/authors?has_books=true").json()] == ["Frank Herbert"]  # INNER JOIN


def test_an_author_keeps_their_one_profile(client, staff):
    author = client.post("/authors", json={"name": "Frank Herbert"}, headers=staff).json()

    client.put(f"/authors/{author['id']}/profile", json={"bio": "First draft."}, headers=staff)
    response = client.put(f"/authors/{author['id']}/profile", json={"bio": "Wrote Dune."}, headers=staff)

    assert response.json()["profile"] == {"bio": "Wrote Dune.", "website": None}


def test_filtering_by_genre_uses_the_junction_table(client, staff):
    author = client.post("/authors", json={"name": "Walt Whitman"}, headers=staff).json()
    poetry = client.post("/genres", json={"name": "poetry"}, headers=staff).json()
    client.post("/books", json={"title": "Leaves of Grass", "author_id": author["id"],
                                "genre_ids": [poetry["id"]], "price": 9.0}, headers=staff)

    assert [b["title"] for b in client.get("/books?genre=poetry").json()] == ["Leaves of Grass"]
    assert client.get("/books?genre=mystery").json() == []