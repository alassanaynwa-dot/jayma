"""Tests du service admin_panel.services.exports — export CSV commissions."""
import pytest
from django.contrib.auth import get_user_model

from admin_panel.services.exports import (
    COMMISSIONS_CSV_COLUMNS,
    commissions_csv_rows,
    filter_commissions_queryset,
)
from commissions.models import Commission
from orders.models import Order
from shops.models import Shop

User = get_user_model()


@pytest.fixture
def shop_with_commissions(db):
    owner = User.objects.create_user(
        username="m1", phone="+221770000010", email="m1@x.sn",
        password="p", role=User.Role.MERCHANT,
    )
    shop = Shop.objects.create(
        owner=owner, name="Boutique X", slug="boutique-x",
        phone="+221770000010", city="Dakar",
        is_approved=True, is_active=True,
    )
    order = Order.objects.create(
        shop=shop, client_name="C", client_phone="+221770003000",
        client_address="r", client_city="Dakar",
        subtotal_xof=10000, total_xof=10000,
        commission_rate=8, commission_xof=800, merchant_amount_xof=9200,
        payment_method=Order.PaymentMethod.WAVE,
        payment_status=Order.PaymentStatus.PAID,
    )
    c_unpaid = Commission.objects.create(
        order=order, shop=shop,
        sale_amount_xof=10000, rate=8,
        commission_xof=800, merchant_amount_xof=9200,
        is_paid=False,
    )

    order2 = Order.objects.create(
        shop=shop, client_name="C2", client_phone="+221770003001",
        client_address="r", client_city="Dakar",
        subtotal_xof=5000, total_xof=5000,
        commission_rate=8, commission_xof=400, merchant_amount_xof=4600,
        payment_method=Order.PaymentMethod.WAVE,
        payment_status=Order.PaymentStatus.PAID,
    )
    c_paid = Commission.objects.create(
        order=order2, shop=shop,
        sale_amount_xof=5000, rate=8,
        commission_xof=400, merchant_amount_xof=4600,
        is_paid=True,
        payout_reference="VIR-2026-001",
    )
    return shop, c_unpaid, c_paid


@pytest.mark.django_db
class TestFilterCommissions:
    def test_filter_unpaid(self, shop_with_commissions):
        qs = filter_commissions_queryset("unpaid")
        assert all(c.is_paid is False for c in qs)
        assert qs.count() == 1

    def test_filter_paid(self, shop_with_commissions):
        qs = filter_commissions_queryset("paid")
        assert all(c.is_paid is True for c in qs)
        assert qs.count() == 1

    def test_filter_all(self, shop_with_commissions):
        qs = filter_commissions_queryset("all")
        assert qs.count() == 2


@pytest.mark.django_db
class TestCsvRows:
    def test_header_row_first(self, shop_with_commissions):
        qs = filter_commissions_queryset("all")
        rows = list(commissions_csv_rows(qs))
        # Première ligne = header CSV
        for col in COMMISSIONS_CSV_COLUMNS:
            assert col in rows[0]

    def test_body_rows_count_matches_queryset(self, shop_with_commissions):
        qs = filter_commissions_queryset("all")
        rows = list(commissions_csv_rows(qs))
        # 1 header + 2 commissions = 3 lignes
        assert len(rows) == 3

    def test_body_contains_payout_reference_when_paid(self, shop_with_commissions):
        qs = filter_commissions_queryset("paid")
        rows = list(commissions_csv_rows(qs))
        body = "\n".join(rows[1:])
        assert "VIR-2026-001" in body

    def test_empty_queryset_only_header(self, db):
        qs = filter_commissions_queryset("paid")  # rien en BDD
        rows = list(commissions_csv_rows(qs))
        assert len(rows) == 1  # juste le header
