"""Dashboard pages for the owner and admins: products, categories and orders."""

import math

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, func, or_, update
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app import forms
from app.database import get_by_id, get_session
from app.deps import request_context, require_staff
from app.enums import (
    ADMIN_ORDER_STATUSES,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    Role,
    Section,
)
from app.images import ImageError, delete_image, save_image, uploaded_files
from app.models import (
    CartItem,
    Category,
    Order,
    OrderItem,
    Product,
    ProductImage,
    User,
    split_list,
    utcnow,
)
from app.orders import cancel_order, mark_paid
from app.payments import release_stale_orders
from app.templating import flash, render

router = APIRouter(
    prefix="/admin", dependencies=[Depends(request_context), Depends(require_staff)]
)

PAGE_SIZE = 30
MAX_IMAGES = 10
MAX_PRICE = 1_000_000_000


def _count(session: Session, statement) -> int:
    return session.exec(select(func.count()).select_from(statement.subquery())).one()


def _page(request: Request) -> int:
    raw = request.query_params.get("page", "1")
    return max(int(raw), 1) if raw.isdigit() and len(raw) <= 6 else 1


def _categories(session: Session) -> list[Category]:
    return list(session.exec(select(Category).order_by(Category.sort_order, Category.name)).all())


def _product_or_404(session: Session, product_id: int) -> Product:
    product = get_by_id(session, Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="المنتج غير موجود")
    return product


def _images_used_by_orders(session: Session, names: list[str]) -> set[str]:
    if not names:
        return set()
    rows = session.exec(select(OrderItem.image).where(OrderItem.image.in_(names))).all()
    return {row for row in rows if row}


# ---------------------------------------------------------------- dashboard


@router.get("")
def dashboard(request: Request, session: Session = Depends(get_session)):
    release_stale_orders(session)
    active_orders = Order.status.not_in([OrderStatus.cancelled, OrderStatus.awaiting_payment])
    stats = {
        "products": _count(session, select(Product)),
        "published": _count(session, select(Product).where(Product.is_published.is_(True))),
        "bala": _count(session, select(Product).where(Product.section == Section.bala)),
        "new_orders": _count(session, select(Order).where(Order.status == OrderStatus.new)),
        "orders": _count(session, select(Order).where(active_orders)),
        "revenue": session.exec(select(func.coalesce(func.sum(Order.total), 0)).where(active_orders)).one(),
        "customers": _count(session, select(User).where(User.role == Role.customer)),
    }
    recent_orders = session.exec(
        select(Order).options(selectinload(Order.items)).order_by(Order.created_at.desc()).limit(8)
    ).all()
    low_stock = session.exec(
        select(Product)
        .options(selectinload(Product.images))
        .where(Product.is_published.is_(True), Product.stock <= 2)
        .order_by(Product.stock, Product.id.desc())
        .limit(8)
    ).all()
    return render(
        request,
        "admin/dashboard.html",
        {"active": "dashboard", "stats": stats, "recent_orders": recent_orders, "low_stock": low_stock},
    )


# ---------------------------------------------------------------- products


@router.get("/products")
def product_list(request: Request, session: Session = Depends(get_session)):
    params = request.query_params
    statement = select(Product)
    query = params.get("q", "").strip()[:80]
    if query:
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        statement = statement.where(Product.name.ilike(f"%{escaped}%", escape="\\"))
    section = params.get("section")
    if section in Section._value2member_map_:
        statement = statement.where(Product.section == Section(section))
    category = get_by_id(session, Category, params.get("category", ""))
    if category:
        statement = statement.where(Product.category_id == category.id)
    if params.get("status") == "hidden":
        statement = statement.where(Product.is_published.is_(False))
    elif params.get("status") == "out":
        statement = statement.where(Product.stock <= 0)

    total = _count(session, statement)
    pages = max(math.ceil(total / PAGE_SIZE), 1)
    page = min(_page(request), pages)
    products = session.exec(
        statement.options(selectinload(Product.images), selectinload(Product.category))
        .order_by(Product.created_at.desc(), Product.id.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    ).all()
    filters = {k: v for k, v in params.items() if k in ("q", "section", "category", "status") and v}
    return render(
        request,
        "admin/products.html",
        {
            "active": "products",
            "products": products,
            "total": total,
            "page": page,
            "pages": pages,
            "filters": filters,
            "categories": _categories(session),
        },
    )


def _product_values(product: Product | None) -> dict:
    if product is None:
        return {
            "name": "",
            "description": "",
            "price": "",
            "old_price": "",
            "section": Section.new.value,
            "category_id": "",
            "sizes": "",
            "colors": "",
            "stock": "1",
            "is_published": True,
            "is_featured": False,
        }
    return {
        "name": product.name,
        "description": product.description,
        "price": str(product.price),
        "old_price": str(product.old_price or ""),
        "section": product.section.value,
        "category_id": str(product.category_id or ""),
        "sizes": product.sizes,
        "colors": product.colors,
        "stock": str(product.stock),
        "is_published": product.is_published,
        "is_featured": product.is_featured,
    }


def _product_form(request, session, product, values, errors, status_code=200):
    return render(
        request,
        "admin/product_form.html",
        {
            "active": "products",
            "product": product,
            "values": values,
            "errors": errors,
            "categories": _categories(session),
            "max_images": MAX_IMAGES,
        },
        status_code=status_code,
    )


def _read_product_form(form, session: Session) -> tuple[dict, dict, dict]:
    values = {
        "name": forms.text(form, "name", 120),
        "description": forms.text(form, "description", 4000),
        "price": forms.text(form, "price", 20),
        "old_price": forms.text(form, "old_price", 20),
        "section": forms.text(form, "section", 10),
        "category_id": forms.text(form, "category_id", 12),
        "sizes": forms.text(form, "sizes", 300),
        "colors": forms.text(form, "colors", 300),
        "stock": forms.text(form, "stock", 10),
        "is_published": forms.checkbox(form, "is_published"),
        "is_featured": forms.checkbox(form, "is_featured"),
    }
    errors: dict[str, str] = {}
    data: dict = {}

    if len(values["name"]) < 2:
        errors["name"] = "اكتب اسم المنتج"
    data["name"] = values["name"]
    data["description"] = values["description"]

    try:
        price = forms.number(form, "price")
    except ValueError:
        price = None
    if price is None or not 0 < price <= MAX_PRICE:
        errors["price"] = "اكتب سعراً صحيحاً بالأرقام"
    data["price"] = price or 0

    try:
        old_price = forms.number(form, "old_price")
    except ValueError:
        old_price = -1
    if old_price == -1 or (old_price is not None and old_price > MAX_PRICE):
        errors["old_price"] = "اكتب السعر بالأرقام"
    elif old_price and price and old_price <= price:
        errors["old_price"] = "السعر قبل الخصم يجب أن يكون أكبر من السعر الحالي"
    data["old_price"] = old_price or None

    try:
        stock = forms.number(form, "stock")
    except ValueError:
        stock = None
    if stock is None or stock > 100_000:
        errors["stock"] = "اكتب الكمية المتوفرة بالأرقام"
    data["stock"] = stock or 0

    if values["section"] not in Section._value2member_map_:
        errors["section"] = "اختر القسم الرئيسي"
    else:
        data["section"] = Section(values["section"])

    data["category_id"] = None
    if values["category_id"]:
        category = get_by_id(session, Category, values["category_id"])
        if category is None:
            errors["category_id"] = "القسم غير موجود"
        else:
            data["category_id"] = category.id

    data["sizes"] = ", ".join(_split(values["sizes"]))
    data["colors"] = ", ".join(_split(values["colors"]))
    data["is_published"] = values["is_published"]
    data["is_featured"] = values["is_featured"]
    return values, errors, data


def _split(raw: str) -> list[str]:
    return [item[:40] for item in split_list(raw)][:20]


async def _save_product(request: Request, session: Session, product: Product | None):
    form = await request.form()
    values, errors, data = _read_product_form(form, session)
    uploads = uploaded_files(form, "images")
    existing = len(product.images) if product else 0
    if existing + len(uploads) > MAX_IMAGES:
        errors["images"] = f"الحد الأقصى {MAX_IMAGES} صور لكل منتج"
    if errors:
        return _product_form(request, session, product, values, errors, status_code=400)

    saved: list[str] = []
    try:
        for upload in uploads:
            saved.append(save_image(session, upload, "products"))
    except ImageError as exc:
        for name in saved:
            delete_image(session, name)
        errors["images"] = str(exc)
        return _product_form(request, session, product, values, errors, status_code=400)

    created = product is None
    if product is None:
        product = Product(**data)
    else:
        for key, value in data.items():
            setattr(product, key, value)
        product.updated_at = utcnow()
    start = max((image.position for image in product.images), default=-1) + 1
    for offset, name in enumerate(saved):
        product.images.append(ProductImage(filename=name, position=start + offset))
    session.add(product)
    session.commit()
    session.refresh(product)
    flash(request, "تم نشر المنتج بنجاح ✨" if created else "تم حفظ التعديلات")
    return RedirectResponse(f"/admin/products/{product.id}", status_code=303)


@router.get("/products/new")
def new_product_page(request: Request, session: Session = Depends(get_session)):
    values = _product_values(None)
    section = request.query_params.get("section")
    if section in Section._value2member_map_:
        values["section"] = section
    return _product_form(request, session, None, values, {})


@router.post("/products/new")
async def create_product(request: Request, session: Session = Depends(get_session)):
    return await _save_product(request, session, None)


@router.get("/products/{product_id}")
def edit_product_page(product_id: int, request: Request, session: Session = Depends(get_session)):
    product = _product_or_404(session, product_id)
    return _product_form(request, session, product, _product_values(product), {})


@router.post("/products/{product_id}")
async def update_product(product_id: int, request: Request, session: Session = Depends(get_session)):
    product = _product_or_404(session, product_id)
    return await _save_product(request, session, product)


@router.post("/products/{product_id}/toggle")
async def toggle_product(product_id: int, request: Request, session: Session = Depends(get_session)):
    product = _product_or_404(session, product_id)
    form = await request.form()
    product.is_published = not product.is_published
    product.updated_at = utcnow()
    session.add(product)
    session.commit()
    flash(request, "المنتج ظاهر الآن في المتجر" if product.is_published else "تم إخفاء المنتج من المتجر")
    return RedirectResponse(
        forms.safe_next(forms.text(form, "next", 300), "/admin/products"), status_code=303
    )


@router.post("/products/{product_id}/delete")
def delete_product(product_id: int, request: Request, session: Session = Depends(get_session)):
    product = _product_or_404(session, product_id)
    names = [image.filename for image in product.images]
    keep = _images_used_by_orders(session, names)
    session.exec(update(OrderItem).where(OrderItem.product_id == product.id).values(product_id=None))
    session.exec(delete(CartItem).where(CartItem.product_id == product.id))
    session.delete(product)
    for name in names:
        if name not in keep:
            delete_image(session, name)
    session.commit()
    flash(request, "تم حذف المنتج")
    return RedirectResponse("/admin/products", status_code=303)


def _image_or_404(product: Product, image_id: int) -> ProductImage:
    image = next((img for img in product.images if img.id == image_id), None)
    if image is None:
        raise HTTPException(status_code=404, detail="الصورة غير موجودة")
    return image


@router.post("/products/{product_id}/images/{image_id}/delete")
def delete_product_image(
    product_id: int, image_id: int, request: Request, session: Session = Depends(get_session)
):
    product = _product_or_404(session, product_id)
    image = _image_or_404(product, image_id)
    name = image.filename
    product.images.remove(image)
    for position, remaining in enumerate(product.images):
        remaining.position = position
    session.add(product)
    if not _images_used_by_orders(session, [name]):
        delete_image(session, name)
    session.commit()
    flash(request, "تم حذف الصورة")
    return RedirectResponse(f"/admin/products/{product.id}#images", status_code=303)


@router.post("/products/{product_id}/images/{image_id}/cover")
def make_cover(product_id: int, image_id: int, request: Request, session: Session = Depends(get_session)):
    product = _product_or_404(session, product_id)
    image = _image_or_404(product, image_id)
    ordered = [image] + [img for img in product.images if img.id != image.id]
    for position, item in enumerate(ordered):
        item.position = position
        session.add(item)
    session.commit()
    flash(request, "تم اختيار الصورة الرئيسية")
    return RedirectResponse(f"/admin/products/{product.id}#images", status_code=303)


# ---------------------------------------------------------------- categories


@router.get("/categories")
def category_list(request: Request, session: Session = Depends(get_session)):
    rows = session.exec(
        select(Category, func.count(Product.id))
        .outerjoin(Product, Product.category_id == Category.id)
        .group_by(Category.id)
        .order_by(Category.sort_order, Category.name)
    ).all()
    return render(
        request,
        "admin/categories.html",
        {"active": "categories", "rows": rows, "errors": {}, "values": {}},
    )


async def _save_category(request: Request, session: Session, category: Category | None):
    form = await request.form()
    name = forms.text(form, "name", 60)
    description = forms.text(form, "description", 300)
    try:
        sort_order = forms.number(form, "sort_order") or 0
    except ValueError:
        sort_order = 0

    error = None
    if len(name) < 2:
        error = "اكتب اسم القسم"
    else:
        clash = session.exec(select(Category).where(func.lower(Category.name) == name.lower())).first()
        if clash and (category is None or clash.id != category.id):
            error = f"القسم «{name}» موجود مسبقاً"

    new_image = None
    uploads = uploaded_files(form, "image")
    if error is None and uploads:
        try:
            new_image = save_image(session, uploads[0], "categories", max_side=1200)
        except ImageError as exc:
            error = str(exc)
    if error:
        flash(request, error, "error")
        return RedirectResponse("/admin/categories", status_code=303)

    created = category is None
    if category is None:
        category = Category(name=name)
    old_image = category.image
    category.name = name
    category.description = description
    category.sort_order = min(sort_order, 9999)
    if new_image:
        category.image = new_image
    elif forms.checkbox(form, "remove_image"):
        category.image = None
    session.add(category)
    if old_image and old_image != category.image:
        delete_image(session, old_image)
    session.commit()
    flash(request, f"تمت إضافة القسم «{name}»" if created else f"تم حفظ القسم «{name}»")
    return RedirectResponse("/admin/categories", status_code=303)


@router.post("/categories")
async def create_category(request: Request, session: Session = Depends(get_session)):
    return await _save_category(request, session, None)


@router.post("/categories/{category_id}")
async def update_category(category_id: int, request: Request, session: Session = Depends(get_session)):
    category = get_by_id(session, Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="القسم غير موجود")
    return await _save_category(request, session, category)


@router.post("/categories/{category_id}/delete")
def delete_category(category_id: int, request: Request, session: Session = Depends(get_session)):
    category = get_by_id(session, Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="القسم غير موجود")
    image = category.image
    session.exec(update(Product).where(Product.category_id == category.id).values(category_id=None))
    session.delete(category)
    delete_image(session, image)
    session.commit()
    flash(request, "تم حذف القسم، وبقيت منتجاته في المتجر بدون قسم")
    return RedirectResponse("/admin/categories", status_code=303)


# ---------------------------------------------------------------- orders


@router.get("/orders")
def order_list(request: Request, session: Session = Depends(get_session)):
    release_stale_orders(session)
    params = request.query_params
    statement = select(Order)
    status = params.get("status")
    if status in OrderStatus._value2member_map_:
        statement = statement.where(Order.status == OrderStatus(status))
    query = forms.western_digits(params.get("q", "").strip()[:40])
    if query:
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        conditions = [
            Order.full_name.ilike(f"%{escaped}%", escape="\\"),
            Order.phone.ilike(f"%{escaped}%", escape="\\"),
        ]
        if query.lstrip("#").isdigit() and len(query) <= 10:
            conditions.append(Order.id == int(query.lstrip("#")))
        statement = statement.where(or_(*conditions))

    total = _count(session, statement)
    pages = max(math.ceil(total / PAGE_SIZE), 1)
    page = min(_page(request), pages)
    orders = session.exec(
        statement.options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    ).all()
    counts = dict(session.exec(select(Order.status, func.count()).group_by(Order.status)).all())
    filters = {k: v for k, v in params.items() if k in ("q", "status") and v}
    return render(
        request,
        "admin/orders.html",
        {
            "active": "orders",
            "orders": orders,
            "total": total,
            "page": page,
            "pages": pages,
            "filters": filters,
            "counts": counts,
        },
    )


def _order_or_404(session: Session, order_id: int) -> Order:
    order = get_by_id(session, Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")
    return order


@router.get("/orders/{order_id}")
def order_detail(order_id: int, request: Request, session: Session = Depends(get_session)):
    order = _order_or_404(session, order_id)
    return render(request, "admin/order.html", {"active": "orders", "order": order})


@router.post("/orders/{order_id}/status")
async def update_order_status(order_id: int, request: Request, session: Session = Depends(get_session)):
    order = _order_or_404(session, order_id)
    form = await request.form()
    target = forms.text(form, "status", 30)
    back = RedirectResponse(f"/admin/orders/{order.id}", status_code=303)

    if target not in {status.value for status in ADMIN_ORDER_STATUSES}:
        flash(request, "اختر حالة صحيحة", "error")
        return back
    target = OrderStatus(target)
    if order.status == OrderStatus.cancelled and target != OrderStatus.cancelled:
        flash(request, "الطلب الملغي لا يمكن إعادة تفعيله، يمكن للزبونة إنشاء طلب جديد", "error")
        return back

    if target == OrderStatus.cancelled:
        cancel_order(session, order)
    else:
        order.status = target
        order.updated_at = utcnow()
        session.add(order)
        session.commit()

    if forms.checkbox(form, "mark_paid") or (
        target == OrderStatus.delivered and order.payment_method == PaymentMethod.cod
    ):
        if order.payment_status != PaymentStatus.paid:
            mark_paid(session, order, "cash" if order.payment_method == PaymentMethod.cod else "manual")
    flash(request, "تم تحديث حالة الطلب")
    return back
