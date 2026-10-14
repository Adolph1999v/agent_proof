from discounts import Order, total_after_discount


def test_large_non_member_does_not_get_member_discount() -> None:
    order = Order(subtotal=150, member=False)
    assert total_after_discount(order) == 150
