from discounts import Order, total_after_discount


def test_large_member_order_gets_ten_percent_discount() -> None:
    order = Order(subtotal=120, member=True)
    assert total_after_discount(order) == 108
