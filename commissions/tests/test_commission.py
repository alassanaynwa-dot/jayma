"""Tests du modèle Commission — snapshot du partage Jappesi/commerçant.

La commission est figée au moment de la confirmation de commande
(snapshot du `rate` et des montants à ce moment-là — pas recalculé
dynamiquement si la commission de la boutique change ensuite).
"""
from decimal import Decimal

import pytest
from django.db import IntegrityError

from commissions.models import Commission
from orders.models import Order
from shops.models import Shop


@pytest.fixture
def shop(db, django_user_model):
    user = django_user_model.objects.create_user(
        username="comm_m", phone="+221770030001", email="cm@x.sn",
        password="pwd", role=django_user_model.Role.MERCHANT,
    )
    return Shop.objects.create(
        owner=user, name="Shop Com", slug="shop-com",
        phone="+221770030001", city="Dakar",
        is_approved=True, is_active=True,
        commission_rate=Decimal("8.00"),
    )


@pytest.fixture
def order(shop):
    return Order.objects.create(
        shop=shop,
        client_name="Test", client_phone="+221770040001",
        client_address="rue", client_city="Dakar",
        subtotal_xof=50000, delivery_xof=0, total_xof=50000,
        commission_rate=Decimal("8.00"),
        commission_xof=4000, merchant_amount_xof=46000,
        payment_method=Order.PaymentMethod.CASH,
        status=Order.Status.PENDING,
    )


@pytest.mark.django_db
class TestCommissionCreation:
    def test_snapshot_amounts_at_creation(self, shop, order):
        c = Commission.objects.create(
            order=order, shop=shop,
            sale_amount_xof=50000,
            rate=Decimal("8.00"),
            commission_xof=4000,
            merchant_amount_xof=46000,
        )
        assert c.pk is not None
        assert c.sale_amount_xof == 50000
        assert c.commission_xof == 4000
        assert c.merchant_amount_xof == 46000
        assert c.is_paid is False
        assert c.paid_at is None
        # Default rate snapshot
        assert c.rate == Decimal("8.00")

    def test_one_commission_per_order(self, shop, order):
        """OneToOneField : impossible d'avoir 2 commissions pour la même order."""
        Commission.objects.create(
            order=order, shop=shop,
            sale_amount_xof=50000, rate=Decimal("8.00"),
            commission_xof=4000, merchant_amount_xof=46000,
        )
        with pytest.raises(IntegrityError):
            Commission.objects.create(
                order=order, shop=shop,
                sale_amount_xof=50000, rate=Decimal("8.00"),
                commission_xof=4000, merchant_amount_xof=46000,
            )

    def test_rate_change_after_does_not_affect_commission(self, shop, order):
        """Si la boutique change son taux après, la commission existante est figée."""
        c = Commission.objects.create(
            order=order, shop=shop,
            sale_amount_xof=50000, rate=Decimal("8.00"),
            commission_xof=4000, merchant_amount_xof=46000,
        )
        # Le commerçant change son taux à 10% plus tard
        shop.commission_rate = Decimal("10.00")
        shop.save()
        c.refresh_from_db()
        # La commission stockée reste à 8%, montants inchangés
        assert c.rate == Decimal("8.00")
        assert c.commission_xof == 4000


@pytest.mark.django_db
class TestCommissionPayout:
    def test_mark_paid_sets_flag_and_timestamp(self, shop, order):
        from django.utils import timezone
        c = Commission.objects.create(
            order=order, shop=shop,
            sale_amount_xof=50000, rate=Decimal("8.00"),
            commission_xof=4000, merchant_amount_xof=46000,
        )
        c.is_paid = True
        c.paid_at = timezone.now()
        c.payout_reference = "WAVE-PAYOUT-2026-001"
        c.save()

        c.refresh_from_db()
        assert c.is_paid is True
        assert c.paid_at is not None
        assert c.payout_reference == "WAVE-PAYOUT-2026-001"

    def test_filter_unpaid_by_shop(self, shop, order):
        Commission.objects.create(
            order=order, shop=shop,
            sale_amount_xof=50000, rate=Decimal("8.00"),
            commission_xof=4000, merchant_amount_xof=46000,
            is_paid=False,
        )
        unpaid = Commission.objects.filter(shop=shop, is_paid=False)
        assert unpaid.count() == 1

    def test_str_representation(self, shop, order):
        c = Commission.objects.create(
            order=order, shop=shop,
            sale_amount_xof=50000, rate=Decimal("8.00"),
            commission_xof=4000, merchant_amount_xof=46000,
        )
        s = str(c)
        assert order.reference in s
        assert "4000" in s
