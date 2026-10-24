import math
from xml.sax.saxutils import escape as xml_escape

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import case, func, or_
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.config import settings
from app.database import get_by_id, get_session
from app.deps import request_context
from app.enums import Section
from app.models import Category, Product, ProductImage
from app.templating import render

router = APIRouter(dependencies=[Depends(request_context)])

PAGE_SIZE = 24
SORTS = {
    "new": "الأحدث",
    "price_asc": "السعر: من الأقل",
    "price_desc": "السعر: من الأعلى",
}


def published():
    return select(Product).where(Product.is_published.is_(True))


def with_images(statement):
    return statement.options(selectinload(Product.images), selectinload(Product.category))


def categories_with_covers(session: Session) -> list[dict]:
    rows = session.exec(
        select(Category, func.count(Product.id))
        .outerjoin(
            Product,
            (Product.category_id == Category.id) & Product.is_published.is_(True),
        )
        .group_by(Category.id)
        .order_by(Category.sort_order, Category.name)
    ).all()
    result = []
    for category, count in rows:
        cover = category.image
        if cover is None:
            cover = session.exec(
                select(ProductImage.filename)
                .join(Product)
                .where(Product.category_id == category.id, Product.is_published.is_(True))
                .order_by(Product.created_at.desc(), ProductImage.position)
                .limit(1)
            ).first()
        result.append({"category": category, "count": count, "cover": cover})
    return result


@router.get("/")
def home(request: Request, session: Session = Depends(get_session)):
    newest = with_images(published().where(Product.section == Section.new))
    new_items = session.exec(
        newest.order_by(Product.is_featured.desc(), Product.created_at.desc()).limit(8)
    ).all()
    bala_items = session.exec(
        with_images(published().where(Product.section == Section.bala))
        .order_by(Product.is_featured.desc(), Product.created_at.desc())
        .limit(6)
    ).all()
    hero_items = session.exec(
        with_images(published().where(Product.images.any()))
        .order_by(Product.is_featured.desc(), Product.created_at.desc())
        .limit(3)
    ).all()
    return render(
        request,
        "shop/home.html",
        {
            "new_items": new_items,
            "bala_items": bala_items,
            "hero_items": hero_items,
            "categories": categories_with_covers(session),
            "counts": {
                "products": session.exec(
                    select(func.count()).select_from(published().where(Product.stock > 0).subquery())
                ).one(),
                "bala": session.exec(
                    select(func.count()).select_from(
                        published()
                        .where(Product.section == Section.bala, Product.stock > 0)
                        .subquery()
                    )
                ).one(),
            },
        },
    )


def _listing(request: Request, session: Session, section: Section | None, template: str):
    params = request.query_params
    if section is None and params.get("section") in Section._value2member_map_:
        section = Section(params["section"])
    category_raw = params.get("category", "")
    category = get_by_id(session, Category, category_raw)
    query = params.get("q", "").strip()[:80]
    sort = params.get("sort") if params.get("sort") in SORTS else "new"
    page_raw = params.get("page", "1")
    page = int(page_raw) if page_raw.isdigit() and 0 < len(page_raw) <= 6 else 1
    page = max(page, 1)

    statement = published()
    if section is not None:
        statement = statement.where(Product.section == section)
    if category is not None:
        statement = statement.where(Product.category_id == category.id)
    if query:
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        statement = statement.where(
            or_(
                Product.name.ilike(pattern, escape="\\"),
                Product.description.ilike(pattern, escape="\\"),
            )
        )

    total = session.exec(select(func.count()).select_from(statement.subquery())).one()
    pages = max(math.ceil(total / PAGE_SIZE), 1)
    page = min(page, pages)

    if sort == "price_asc":
        order = (Product.price.asc(), Product.id.desc())
    elif sort == "price_desc":
        order = (Product.price.desc(), Product.id.desc())
    else:
        order = (Product.created_at.desc(), Product.id.desc())
    products = session.exec(
        with_images(statement).order_by(*order).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    ).all()

    filters = {
        key: value
        for key, value in {
            "section": section.value if section and template == "shop/list.html" else "",
            "category": category.id if category else "",
            "q": query,
            "sort": sort if sort != "new" else "",
        }.items()
        if value
    }
    return render(
        request,
        template,
        {
            "products": products,
            "total": total,
            "page": page,
            "pages": pages,
            "section": section,
            "category": category,
            "query": query,
            "sort": sort,
            "sorts": SORTS,
            "filters": filters,
            "categories": session.exec(
                select(Category).order_by(Category.sort_order, Category.name)
            ).all(),
        },
    )


@router.get("/shop")
def shop(request: Request, session: Session = Depends(get_session)):
    return _listing(request, session, None, "shop/list.html")


@router.get("/bala")
def bala(request: Request, session: Session = Depends(get_session)):
    return _listing(request, session, Section.bala, "shop/bala.html")


@router.get("/product/{product_id}")
def product_detail(product_id: int, request: Request, session: Session = Depends(get_session)):
    product = get_by_id(session, Product, product_id)
    viewer = request.state.user
    if product is None or (not product.is_published and not (viewer and viewer.is_staff)):
        raise HTTPException(status_code=404, detail="هذا المنتج غير موجود")

    related_query = with_images(
        published().where(Product.id != product.id, Product.section == product.section)
    )
    if product.category_id is not None:
        related_query = related_query.order_by(
            case((Product.category_id == product.category_id, 0), else_=1)
        )
    related = session.exec(related_query.order_by(Product.created_at.desc()).limit(4)).all()
    return render(request, "shop/product.html", {"product": product, "related": related})


@router.get("/about")
def about(request: Request):
    return render(request, "shop/about.html")


@router.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return (
        "User-agent: *\nDisallow: /admin\nDisallow: /account\nDisallow: /checkout\nDisallow: /cart\n"
        f"Sitemap: {settings.base_url.rstrip('/')}/sitemap.xml\n"
    )


@router.get("/sitemap.xml")
def sitemap(session: Session = Depends(get_session)):
    """Lists every public page so search engines can find the whole shop."""
    base = settings.base_url.rstrip("/")
    entries = [(f"{base}{path}", None) for path in ("/", "/shop", "/shop?section=new", "/bala", "/about")]
    for category_id in session.exec(select(Category.id).order_by(Category.sort_order)).all():
        entries.append((f"{base}/shop?category={category_id}", None))
    for product_id, updated in session.exec(
        select(Product.id, Product.updated_at).where(Product.is_published.is_(True)).order_by(Product.id)
    ).all():
        entries.append((f"{base}/product/{product_id}", updated))

    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url, updated in entries:
        lastmod = f"<lastmod>{updated.date().isoformat()}</lastmod>" if updated else ""
        lines.append(f"<url><loc>{xml_escape(url)}</loc>{lastmod}</url>")
    lines.append("</urlset>")
    return Response("\n".join(lines), media_type="application/xml")
