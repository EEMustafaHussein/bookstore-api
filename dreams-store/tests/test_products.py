from sqlmodel import select

from app.config import settings
from app.enums import Role, Section
from app.models import Category, Product
from tests.conftest import image_file, login, make_product, make_user, post


def staff_login(client, db, role=Role.admin):
    make_user(db, email="staff@example.com", role=role)
    login(client, "staff@example.com")


def product_form(**overrides):
    data = {
        "name": "فستان ستان",
        "description": "قماش ستان ناعم\nمناسب للسهرات",
        "price": "٣٥,٠٠٠",
        "old_price": "45000",
        "section": "new",
        "category_id": "",
        "sizes": "S, M، L",
        "colors": "وردي, أسود",
        "stock": "4",
        "is_published": "on",
    }
    data.update(overrides)
    return data


def test_admin_publishes_product_with_images(client, db):
    staff_login(client, db)
    response = post(
        client,
        "/admin/products/new",
        product_form(),
        files=[("images", image_file("a.jpg")), ("images", image_file("b.png", fmt="PNG"))],
    )
    assert response.status_code == 303, response.text
    product = db.exec(select(Product)).one()
    assert product.price == 35000 and product.old_price == 45000
    assert product.size_list == ["S", "M", "L"] and product.color_list == ["وردي", "أسود"]
    assert len(product.images) == 2
    for image in product.images:
        path = settings.media_dir / image.filename
        assert path.exists() and path.suffix == ".webp"

    page = client.get(f"/product/{product.id}")
    assert page.status_code == 200
    assert "فستان ستان" in page.text and "35,000" in page.text and "خصم 22%" in page.text
    assert "مناسب للسهرات" in page.text
    assert client.get(f"/media/{product.images[0].filename}").status_code == 200


def test_product_validation(client, db):
    staff_login(client, db)
    response = post(client, "/admin/products/new", product_form(name="", price="abc", old_price="100", stock="-1"))
    assert response.status_code == 400
    assert "اكتب اسم المنتج" in response.text and "اكتب سعراً صحيحاً" in response.text
    response = post(client, "/admin/products/new", product_form(price="50000", old_price="40000"))
    assert response.status_code == 400 and "أكبر من السعر الحالي" in response.text
    assert db.exec(select(Product)).first() is None


def test_bad_image_is_rejected_and_nothing_is_saved(client, db):
    staff_login(client, db)
    response = post(
        client,
        "/admin/products/new",
        product_form(),
        files=[("images", image_file("ok.jpg")), ("images", ("evil.jpg", b"<?php echo 1;", "image/jpeg"))],
    )
    assert response.status_code == 400 and "ليس صورة صالحة" in response.text
    assert db.exec(select(Product)).first() is None
    assert not any((settings.media_dir / "products").glob("*.webp"))


def test_edit_cover_and_delete_images(client, db):
    staff_login(client, db)
    post(client, "/admin/products/new", product_form(), files=[("images", image_file("a.jpg")), ("images", image_file("b.jpg"))])
    product = db.exec(select(Product)).one()
    first, second = product.images
    first_id, first_file, second_id = first.id, first.filename, second.id

    post(client, f"/admin/products/{product.id}", product_form(price="30000", old_price="", section="bala", stock="1"))
    db.refresh(product)
    assert product.price == 30000 and product.old_price is None and product.section == Section.bala

    post(client, f"/admin/products/{product.id}/images/{second_id}/cover")
    db.expire_all()
    assert product.images[0].id == second_id

    post(client, f"/admin/products/{product.id}/images/{first_id}/delete")
    db.expire_all()
    assert [img.id for img in product.images] == [second_id]
    assert not (settings.media_dir / first_file).exists()


def test_toggle_and_delete_product(client, db):
    staff_login(client, db)
    product = make_product(db)
    product_id = product.id
    response = post(client, f"/admin/products/{product_id}/toggle", {"next": "/admin/products?q=x"})
    assert response.headers["location"] == "/admin/products?q=x"
    db.refresh(product)
    assert not product.is_published
    response = post(client, f"/admin/products/{product_id}/delete")
    assert response.status_code == 303
    db.expire_all()
    assert db.get(Product, product_id) is None
    assert post(client, "/admin/products/99999/delete").status_code == 404


def test_categories_crud(client, db):
    staff_login(client, db)
    post(client, "/admin/categories", {"name": "فساتين", "description": "كل الفساتين", "sort_order": "1"}, files=[("image", image_file())])
    post(client, "/admin/categories", {"name": "فساتين"})
    categories = db.exec(select(Category)).all()
    assert len(categories) == 1 and categories[0].image

    category = categories[0]
    category_id = category.id
    product = make_product(db)
    product_id = product.id
    product.category_id = category.id
    db.add(product)
    db.commit()
    assert "فساتين" in client.get("/").text
    assert "فستان وردي" in client.get(f"/shop?category={category.id}").text

    post(client, f"/admin/categories/{category.id}", {"name": "فساتين سهرة", "sort_order": "2", "remove_image": "on"})
    db.refresh(category)
    assert category.name == "فساتين سهرة" and category.image is None

    post(client, f"/admin/categories/{category_id}/delete")
    db.expire_all()
    assert db.get(Category, category_id) is None
    assert db.get(Product, product_id).category_id is None


def test_admin_product_list_filters(client, db):
    staff_login(client, db)
    make_product(db, name="قطعة بالة", section=Section.bala)
    make_product(db, name="قطعة مخفية", published=False)
    assert "قطعة بالة" in client.get("/admin/products?section=bala").text
    hidden = client.get("/admin/products?status=hidden").text
    assert "قطعة مخفية" in hidden and "قطعة بالة" not in hidden
