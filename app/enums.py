from enum import Enum


class Role(str, Enum):
    admin = "admin"
    staff = "staff"
    customer = "customer"


class Genre(str, Enum):
    fiction = "fiction"
    non_fiction = "non_fiction"
    science = "science"
    history = "history"
    fantasy = "fantasy"


class OrderStatus(str, Enum):
    pending = "pending"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"