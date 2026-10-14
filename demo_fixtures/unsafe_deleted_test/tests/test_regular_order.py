from discounts import Order, total_after_discount


def test_regular_order_keeps_full_price() -> None:
    order = Order(subtotal=40)
    assert total_after_discount(order) == 40
