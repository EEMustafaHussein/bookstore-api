from datetime import datetime, timezone

from sqlmodel import Field, Relationship, SQLModel

from app.enums import OrderStatus, PaymentMethod, PaymentStatus, Role, Section


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=80)
    email: str = Field(unique=True, index=True, max_length=254)
    phone: str = Field(default="", max_length=20)
    hashed_password: str
    role: Role = Field(default=Role.customer, index=True)
    is_active: bool = True
    created_at: datetime = Field(default_factory=utcnow)

    @property
    def is_staff(self) -> bool:
        return self.role in (Role.owner, Role.admin)

    @property
    def is_owner(self) -> bool:
        return self.role == Role.owner


class Category(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, max_length=60)
    description: str = Field(default="", max_length=300)
    image: str | None = None
    sort_order: int = 0
    created_at: datetime = Field(default_factory=utcnow)

    products: list["Product"] = Relationship(back_populates="category")


class Product(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=120, index=True)
    description: str = Field(default="", max_length=4000)
    price: int
    old_price: int | None = None
    section: Section = Field(default=Section.new, index=True)
    category_id: int | None = Field(
        default=None, foreign_key="category.id", ondelete="SET NULL", index=True
    )
    sizes: str = Field(default="", max_length=300)
    colors: str = Field(default="", max_length=300)
    stock: int = 1
    is_published: bool = Field(default=True, index=True)
    is_featured: bool = False
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow)

    category: Category | None = Relationship(back_populates="products")
    images: list["ProductImage"] = Relationship(
        back_populates="product",
        sa_relationship_kwargs={
            "order_by": "ProductImage.position",
            "cascade": "all, delete-orphan",
        },
    )

    @property
    def size_list(self) -> list[str]:
        return split_list(self.sizes)

    @property
    def color_list(self) -> list[str]:
        return split_list(self.colors)

    @property
    def cover(self) -> str | None:
        return self.images[0].filename if self.images else None

    @property
    def hover_image(self) -> str | None:
        return self.images[1].filename if len(self.images) > 1 else None

    @property
    def discount_percent(self) -> int:
        if self.old_price and self.old_price > self.price:
            return round((self.old_price - self.price) * 100 / self.old_price)
        return 0

    @property
    def in_stock(self) -> bool:
        return self.stock > 0


class ProductImage(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id", ondelete="CASCADE", index=True)
    filename: str
    position: int = 0

    product: Product = Relationship(back_populates="images")


class CartItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    # A cart belongs to a signed-in user, or to a visitor through a random token in their session.
    user_id: int | None = Field(default=None, foreign_key="user.id", ondelete="CASCADE", index=True)
    cart_token: str | None = Field(default=None, index=True, max_length=64)
    product_id: int = Field(foreign_key="product.id", ondelete="CASCADE", index=True)
    size: str = ""
    color: str = ""
    quantity: int = 1
    created_at: datetime = Field(default_factory=utcnow)

    product: Product = Relationship()


class Order(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    status: OrderStatus = Field(default=OrderStatus.new, index=True)
    payment_method: PaymentMethod = PaymentMethod.cod
    payment_status: PaymentStatus = PaymentStatus.unpaid
    payment_provider: str = ""
    payment_reference: str = Field(default="", index=True)

    full_name: str = Field(max_length=80)
    phone: str = Field(max_length=20)
    governorate: str = Field(max_length=40)
    city: str = Field(max_length=80)
    address: str = Field(max_length=300)
    notes: str = Field(default="", max_length=500)

    subtotal: int
    shipping_fee: int
    total: int

    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow)
    paid_at: datetime | None = None

    user: User = Relationship()
    items: list["OrderItem"] = Relationship(
        back_populates="order", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

    @property
    def item_count(self) -> int:
        return sum(item.quantity for item in self.items)

    @property
    def can_be_cancelled_by_customer(self) -> bool:
        # Paid orders need a refund, so only the shop can cancel them.
        return (
            self.status in (OrderStatus.awaiting_payment, OrderStatus.new)
            and self.payment_status == PaymentStatus.unpaid
        )


class OrderItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="order.id", ondelete="CASCADE", index=True)
    # Kept even after the product is deleted, so old orders still show what was bought.
    product_id: int | None = Field(
        default=None, foreign_key="product.id", ondelete="SET NULL", index=True
    )
    product_name: str
    image: str | None = None
    unit_price: int
    size: str = ""
    color: str = ""
    quantity: int
    line_total: int

    order: Order = Relationship(back_populates="items")


class MediaFile(SQLModel, table=True):
    """An uploaded photo, when MEDIA_STORAGE=database."""

    __tablename__ = "media_file"

    name: str = Field(primary_key=True, max_length=120)
    content_type: str = "image/webp"
    data: bytes
    created_at: datetime = Field(default_factory=utcnow)


class SiteSetting(SQLModel, table=True):
    key: str = Field(primary_key=True, max_length=60)
    value: str


def split_list(raw: str) -> list[str]:
    seen: list[str] = []
    for part in raw.replace("،", ",").split(","):
        part = part.strip()
        if part and part not in seen:
            seen.append(part)
    return seen
