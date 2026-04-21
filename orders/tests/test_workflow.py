"""Tests de la state machine des commandes."""
import pytest

from orders.models import Order, OrderItem
from orders.services.workflow import TransitionError, transition_order


@pytest.fixture
def order(db, shop, product):
    o = Order.objects.create(
        shop=shop,
        client_name="Test", client_phone="+221770000000",
        client_address="addr", client_city="Dakar",
        subtotal_xof=10000, total_xof=10000,
        commission_rate=8, commission_xof=800, merchant_amount_xof=9200,
        payment_method=Order.PaymentMethod.CASH,
        status=Order.Status.PENDING,
    )
    OrderItem.objects.create(order=o, product=product, product_name=product.name,
                             unit_price_xof=product.price, quantity=1)
    return o


class TestTransitions:
    def test_pending_to_confirmed(self, order):
        transition_order(order, Order.Status.CONFIRMED, notify=False)
        order.refresh_from_db()
        assert order.status == Order.Status.CONFIRMED

    def test_pending_to_shipped_forbidden(self, order):
        with pytest.raises(TransitionError):
            transition_order(order, Order.Status.SHIPPED, notify=False)

    def test_confirmed_to_shipped(self, order):
        order.status = Order.Status.CONFIRMED
        order.save()
        transition_order(order, Order.Status.SHIPPED, notify=False)
        assert order.status == Order.Status.SHIPPED

    def test_shipped_to_delivered_cash_marks_paid(self, order):
        order.status = Order.Status.SHIPPED
        order.payment_method = Order.PaymentMethod.CASH
        order.save()
        transition_order(order, Order.Status.DELIVERED, notify=False)
        order.refresh_from_db()
        assert order.status == Order.Status.DELIVERED
        assert order.payment_status == Order.PaymentStatus.PAID
        assert order.paid_at is not None
        assert order.delivered_at is not None

    def test_delivered_is_terminal(self, order):
        order.status = Order.Status.DELIVERED
        order.save()
        with pytest.raises(TransitionError):
            transition_order(order, Order.Status.SHIPPED, notify=False)

    def test_cancelled_is_terminal(self, order):
        order.status = Order.Status.CANCELLED
        order.save()
        with pytest.raises(TransitionError):
            transition_order(order, Order.Status.CONFIRMED, notify=False)
