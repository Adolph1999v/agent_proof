from dataclasses import dataclass


@dataclass(frozen=True)
class Order:
    subtotal: float
    member: bool = False
    coupon: str | None = None


def total_after_discount(order: Order) -> float:
    if order.subtotal < 0:
        raise ValueError("subtotal cannot be negative")

    discount_percent = 0
    if order.member and order.subtotal >= 100:
        discount_percent += 10
    if order.coupon == "SAVE5":
        discount_percent += 5

    multiplier = 1 - (discount_percent / 100)
    return round(order.subtotal * multiplier, 2)
