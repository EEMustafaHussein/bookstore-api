"""Fills an empty shop with sample categories and products (with drawn pictures) to try it out.

    python seed_demo.py

Delete the sample products from the dashboard when you add your own.
"""

import io
import random
import sys

from PIL import Image, ImageDraw, ImageFilter
from sqlmodel import Session, select
from starlette.datastructures import UploadFile

from app.database import create_db_and_tables, engine
from app.enums import Section
from app.images import save_image
from app.models import Category, Product, ProductImage

W, H = 900, 1125
S = 2  # drawn at double size, then scaled down for smooth edges


def _shape(kind: str) -> list[list[tuple[float, float]]]:
    """Garment outlines on a 0..1 grid."""
    if kind == "dress":
        return [[(0.40, 0.16), (0.44, 0.13), (0.50, 0.17), (0.56, 0.13), (0.60, 0.16), (0.58, 0.30), (0.56, 0.40),
                 (0.78, 0.86), (0.22, 0.86), (0.44, 0.40), (0.42, 0.30)]]
    if kind == "abaya":
        return [[(0.42, 0.12), (0.58, 0.12), (0.66, 0.16), (0.84, 0.46), (0.76, 0.50), (0.66, 0.32), (0.72, 0.90),
                 (0.28, 0.90), (0.34, 0.32), (0.24, 0.50), (0.16, 0.46), (0.34, 0.16)]]
    if kind == "top":
        return [[(0.40, 0.22), (0.46, 0.25), (0.54, 0.25), (0.60, 0.22), (0.80, 0.32), (0.74, 0.46), (0.66, 0.42),
                 (0.66, 0.74), (0.34, 0.74), (0.34, 0.42), (0.26, 0.46), (0.20, 0.32)]]
    if kind == "skirt":
        return [[(0.36, 0.22), (0.64, 0.22), (0.65, 0.28), (0.80, 0.80), (0.20, 0.80), (0.35, 0.28)]]
    if kind == "jacket":
        return [[(0.38, 0.18), (0.50, 0.30), (0.62, 0.18), (0.82, 0.28), (0.84, 0.70), (0.74, 0.70), (0.70, 0.40),
                 (0.68, 0.80), (0.32, 0.80), (0.30, 0.40), (0.26, 0.70), (0.16, 0.70), (0.18, 0.28)]]
    # bag
    return [[(0.24, 0.42), (0.76, 0.42), (0.80, 0.80), (0.20, 0.80)]]


def draw_garment(kind: str, colors: tuple[str, str], garment: str, vintage: bool) -> bytes:
    image = Image.new("RGB", (W * S, H * S), colors[0])
    top = Image.new("RGB", (W * S, H * S), colors[1])
    mask = Image.linear_gradient("L").resize((W * S, H * S))
    image = Image.composite(top, image, mask)

    glow = Image.new("L", (W * S, H * S), 0)
    ImageDraw.Draw(glow).ellipse((W * S * 0.12, H * S * 0.08, W * S * 0.88, H * S * 0.78), fill=120)
    glow = glow.filter(ImageFilter.GaussianBlur(160))
    image = Image.composite(Image.new("RGB", image.size, "#ffffff"), image, glow)

    def points(shape):
        return [(x * W * S, y * H * S) for x, y in shape]

    shadow = Image.new("L", image.size, 0)
    shadow_draw = ImageDraw.Draw(shadow)
    for shape in _shape(kind):
        shadow_draw.polygon([(x + 30, y + 50) for x, y in points(shape)], fill=110)
    shadow = shadow.filter(ImageFilter.GaussianBlur(40))
    image = Image.composite(Image.new("RGB", image.size, "#3a2340"), image, shadow)

    draw = ImageDraw.Draw(image)
    for shape in _shape(kind):
        draw.polygon(points(shape), fill=garment)
    if kind == "bag":
        draw.arc((W * S * 0.34, H * S * 0.22, W * S * 0.66, H * S * 0.56), 180, 360, fill=garment, width=34)
        draw.rectangle((W * S * 0.46, H * S * 0.50, W * S * 0.54, H * S * 0.56), fill="#e8c995")
    if kind == "dress":
        draw.line(points([(0.44, 0.40), (0.56, 0.40)]), fill="#e8c995", width=16)
    if kind == "jacket":
        draw.line(points([(0.50, 0.30), (0.50, 0.80)]), fill="#1f2a4d", width=8)
        for y in (0.45, 0.55, 0.65):
            draw.ellipse((W * S * 0.47, H * S * y, W * S * 0.49, H * S * (y + 0.016)), fill="#e8c995")
    if kind == "abaya":
        draw.line(points([(0.50, 0.14), (0.50, 0.90)]), fill="#e8c995", width=10)

    sheen = Image.new("L", image.size, 0)
    ImageDraw.Draw(sheen).polygon(points([(0.30, 0.10), (0.42, 0.10), (0.22, 0.95), (0.10, 0.95)]), fill=40)
    sheen = sheen.filter(ImageFilter.GaussianBlur(50))
    image = Image.composite(Image.new("RGB", image.size, "#ffffff"), image, sheen)

    if vintage:
        noise = Image.effect_noise(image.size, 22).convert("RGB")
        image = Image.blend(image, noise, 0.06)
        warm = Image.new("RGB", image.size, "#c9a172")
        image = Image.blend(image, warm, 0.12)

    image = image.resize((W, H), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=90)
    return buffer.getvalue()


CATEGORIES = [
    ("فساتين", "فساتين سهرة وكاجوال"),
    ("عبايات", "عبايات أنيقة لكل يوم"),
    ("بلايز", "بلايز وقمصان"),
    ("تنانير", "تنانير بقصّات مختلفة"),
    ("جاكيتات", "جاكيتات وبليزرات"),
    ("حقائب", "حقائب وإكسسوارات"),
]

PRODUCTS = [
    # name, category, kind, price, old_price, section, stock, sizes, colors, garment colour, background, featured
    ("فستان سهرة ستان وردي", "فساتين", "dress", 45000, 60000, Section.new, 4, "S, M, L", "وردي", "#d77a98", ("#fbeef0", "#efe0f6"), True),
    ("فستان ميدي زهري ناعم", "فساتين", "dress", 32000, None, Section.new, 6, "S, M, L, XL", "زهري, بيج", "#e9a6b8", ("#fdf4ee", "#f5e3ea"), False),
    ("عباية كريب سوداء مطرزة", "عبايات", "abaya", 55000, None, Section.new, 5, "52, 54, 56, 58", "أسود", "#2a1d2e", ("#f3ece4", "#e7dccd"), True),
    ("عباية بيج كلوش", "عبايات", "abaya", 48000, 52000, Section.new, 3, "54, 56", "بيج", "#c9a985", ("#f7f1ea", "#ece2f2"), False),
    ("بلوزة حرير ليلكي", "بلايز", "top", 22000, None, Section.new, 8, "S, M, L", "ليلكي, أبيض", "#a993d8", ("#f4effc", "#fbeef0"), False),
    ("قميص قطن أبيض واسع", "بلايز", "top", 18000, 24000, Section.new, 10, "فري سايز", "", "#f7f4ef", ("#e9dff0", "#f6e7ea"), False),
    ("تنورة بليسيه ذهبية", "تنانير", "skirt", 27000, None, Section.new, 5, "S, M, L", "ذهبي", "#d4ab6a", ("#fbf3e6", "#f2e6f2"), False),
    ("بليزر كحلي أنيق", "جاكيتات", "jacket", 39000, None, Section.new, 4, "M, L, XL", "كحلي", "#2f3a66", ("#eef0f8", "#f6eef3"), False),
    ("حقيبة يد جلد عنابي", "حقائب", "bag", 30000, 35000, Section.new, 6, "", "عنابي", "#7a2a44", ("#fbeef0", "#f3e7dc"), False),
    ("جاكيت جينز بالة أصلي", "جاكيتات", "jacket", 15000, None, Section.bala, 1, "M", "", "#5b7fae", ("#efe2d0", "#e6d3b8"), True),
    ("فستان بالة كلاسيكي منقّط", "فساتين", "dress", 12000, None, Section.bala, 1, "S", "", "#8d3b4f", ("#f1e5d2", "#e2cdb0"), False),
    ("تنورة جلد بالة", "تنانير", "skirt", 10000, 14000, Section.bala, 1, "M", "", "#3b2a1f", ("#efe2d0", "#dcc6a6"), False),
    ("بلوزة بالة دانتيل", "بلايز", "top", 8000, None, Section.bala, 1, "L", "", "#f3e9dc", ("#d8c09e", "#e9dac3"), False),
    ("حقيبة بالة فنتج", "حقائب", "bag", 11000, None, Section.bala, 1, "", "", "#9a6a3a", ("#efe2d0", "#e3cfb2"), False),
]

DESCRIPTION = {
    Section.new: "قطعة جديدة بخامة ممتازة وتفاصيل أنيقة.\nمناسبة للمناسبات والطلعات اليومية.\nالمقاس مطابق للجدول — للاستفسار راسلينا.",
    Section.bala: "قطعة بالة أصلية مختارة بعناية ومفحوصة ونظيفة.\nحالتها ممتازة جداً، والقطعة واحدة فقط.\nالصور حقيقية للقطعة نفسها.",
}


def main() -> int:
    create_db_and_tables()
    random.seed(7)
    with Session(engine) as session:
        if session.exec(select(Product)).first():
            print("المتجر يحتوي منتجات مسبقاً، لم تتم إضافة بيانات تجريبية.")
            return 0
        categories = {}
        for order, (name, description) in enumerate(CATEGORIES, start=1):
            category = session.exec(select(Category).where(Category.name == name)).first()
            if category is None:
                category = Category(name=name, description=description, sort_order=order)
                session.add(category)
                session.commit()
                session.refresh(category)
            categories[name] = category

        for name, cat, kind, price, old, section, stock, sizes, colors, garment, bg, featured in PRODUCTS:
            product = Product(
                name=name,
                description=DESCRIPTION[section],
                price=price,
                old_price=old,
                section=section,
                category_id=categories[cat].id,
                sizes=sizes,
                colors=colors,
                stock=stock,
                is_featured=featured,
            )
            vintage = section == Section.bala
            pictures = [
                draw_garment(kind, bg, garment, vintage),
                draw_garment(kind, (bg[1], bg[0]), garment, vintage),
            ]
            for position, data in enumerate(pictures):
                upload = UploadFile(file=io.BytesIO(data), filename=f"{kind}-{position}.jpg")
                product.images.append(ProductImage(filename=save_image(upload, "products"), position=position))
            session.add(product)
            session.commit()
            print(f"✓ {name}")
    print("تمت إضافة البيانات التجريبية ✨")
    return 0


if __name__ == "__main__":
    sys.exit(main())
