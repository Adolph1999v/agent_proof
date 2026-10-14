from discounts import Order, total_after_discount


def test_coupon_discount_still_applies() -> None:
    order = Order(subtotal=80, coupon="SAVE5")
    assert total_after_discount(order) == 76
