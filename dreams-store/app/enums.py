from enum import Enum


class Role(str, Enum):
    owner = "owner"
    admin = "admin"
    customer = "customer"


class Section(str, Enum):
    new = "new"
    bala = "bala"


class OrderStatus(str, Enum):
    awaiting_payment = "awaiting_payment"
    new = "new"
    confirmed = "confirmed"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"


class PaymentMethod(str, Enum):
    cod = "cod"
    card = "card"


class PaymentStatus(str, Enum):
    unpaid = "unpaid"
    paid = "paid"


ROLE_LABELS = {
    Role.owner: "المالك",
    Role.admin: "مسؤول",
    Role.customer: "زبونة",
}

SECTION_LABELS = {
    Section.new: "جديد",
    Section.bala: "بالة",
}

ORDER_STATUS_LABELS = {
    OrderStatus.awaiting_payment: "بانتظار الدفع",
    OrderStatus.new: "طلب جديد",
    OrderStatus.confirmed: "تم التأكيد",
    OrderStatus.shipped: "قيد التوصيل",
    OrderStatus.delivered: "تم التسليم",
    OrderStatus.cancelled: "ملغي",
}

PAYMENT_METHOD_LABELS = {
    PaymentMethod.cod: "الدفع عند الاستلام",
    PaymentMethod.card: "بطاقة بنكية (ماستر كارد / فيزا)",
}

PAYMENT_STATUS_LABELS = {
    PaymentStatus.unpaid: "غير مدفوع",
    PaymentStatus.paid: "مدفوع",
}

# Statuses an admin can move an order to by hand. "awaiting_payment" is only set by checkout.
ADMIN_ORDER_STATUSES = [
    OrderStatus.new,
    OrderStatus.confirmed,
    OrderStatus.shipped,
    OrderStatus.delivered,
    OrderStatus.cancelled,
]

GOVERNORATES = [
    "بغداد",
    "البصرة",
    "نينوى",
    "أربيل",
    "النجف",
    "كربلاء",
    "بابل",
    "ذي قار",
    "الأنبار",
    "ديالى",
    "كركوك",
    "صلاح الدين",
    "واسط",
    "ميسان",
    "المثنى",
    "القادسية",
    "دهوك",
    "السليمانية",
    "حلبجة",
]
