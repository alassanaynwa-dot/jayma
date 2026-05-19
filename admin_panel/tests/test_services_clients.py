"""Tests du service admin_panel.services.clients.

Testé en unitaire (sans Client HTTP) pour pouvoir varier les inputs vite.
"""
import pytest
from django.contrib.auth import get_user_model

from admin_panel.services.clients import list_top_clients
from orders.models import Order
from shops.models import Shop

User = get_user_model()


@pytest.fixture
def two_shops_with_orders(db):
    owner1 = User.objects.create_user(
        username="o1", phone="+221770000001", email="o1@x.sn",
        password="p", role=User.Role.MERCHANT,
    )
    owner2 = User.objects.create_user(
        username="o2", phone="+221770000002", email="o2@x.sn",
        password="p", role=User.Role.MERCHANT,
    )
    s1 = Shop.objects.create(
        owner=owner1, name="S1", slug="s1", phone="+221770000001",
        city="Dakar", is_approved=True, is_active=True,
    )
    s2 = Shop.objects.create(
        owner=owner2, name="S2", slug="s2", phone="+221770000002",
        city="Dakar", is_approved=True, is_active=True,
    )

    # Client A : 3 commandes sur S1, total 30000
    for i in range(3):
        Order.objects.create(
            shop=s1, client_name="Aïssatou D.", client_phone="+221770010000",
            client_address="r", client_city="Dakar",
            subtotal_xof=10000, total_xof=10000,
            commission_rate=8, commission_xof=800, merchant_amount_xof=9200,
            payment_method=Order.PaymentMethod.WAVE,
            payment_status=Order.PaymentStatus.PAID if i < 2 else Order.PaymentStatus.PENDING,
        )

    # Client B : 1 commande sur S1 + 1 sur S2 (cross-boutique), total 5000
    Order.objects.create(
        shop=s1, client_name="Fatou N.", client_phone="+221770020000",
        client_address="r", client_city="Dakar",
        subtotal_xof=2000, total_xof=2000,
        commission_rate=8, commission_xof=160, merchant_amount_xof=1840,
        payment_method=Order.PaymentMethod.CASH,
        payment_status=Order.PaymentStatus.PAID,
    )
    Order.objects.create(
        shop=s2, client_name="Fatou Ndiaye", client_phone="+221770020000",
        client_address="r", client_city="Dakar",
        subtotal_xof=3000, total_xof=3000,
        commission_rate=8, commission_xof=240, merchant_amount_xof=2760,
        payment_method=Order.PaymentMethod.CASH,
        payment_status=Order.PaymentStatus.PAID,
    )
    return s1, s2


@pytest.mark.django_db
class TestListTopClients:
    def test_aggregates_by_phone_across_shops(self, two_shops_with_orders):
        """Le même téléphone sur 2 boutiques différentes = 1 entrée client agrégée."""
        clients = list_top_clients()
        phones = [c["phone"] for c in clients]
        assert "+221770010000" in phones
        assert "+221770020000" in phones
        # Pas de doublon pour Fatou (présente sur 2 shops)
        assert phones.count("+221770020000") == 1

    def test_sorted_by_total_spent_desc(self, two_shops_with_orders):
        clients = list_top_clients()
        # Aïssatou (30000) > Fatou (5000)
        assert clients[0]["phone"] == "+221770010000"
        assert clients[0]["total_spent"] == 30000
        assert clients[1]["phone"] == "+221770020000"
        assert clients[1]["total_spent"] == 5000

    def test_shops_count_distinct(self, two_shops_with_orders):
        """Fatou a commandé sur 2 boutiques → shops_count=2."""
        clients = list_top_clients()
        fatou = next(c for c in clients if c["phone"] == "+221770020000")
        assert fatou["shops_count"] == 2

    def test_paid_count_excludes_pending(self, two_shops_with_orders):
        """Aïssatou : 2 commandes payées sur 3 (la 3e est pending)."""
        clients = list_top_clients()
        aissatou = next(c for c in clients if c["phone"] == "+221770010000")
        assert aissatou["orders_count"] == 3
        assert aissatou["paid_count"] == 2

    def test_last_name_from_most_recent_order(self, two_shops_with_orders):
        """Fatou : nom le plus récent = 'Fatou Ndiaye' (le 2e order, sur S2)."""
        clients = list_top_clients()
        fatou = next(c for c in clients if c["phone"] == "+221770020000")
        assert fatou["name"] == "Fatou Ndiaye"

    def test_filter_q_by_name(self, two_shops_with_orders):
        clients = list_top_clients(q="Aïssatou")
        assert len(clients) == 1
        assert clients[0]["phone"] == "+221770010000"

    def test_filter_q_by_phone_partial(self, two_shops_with_orders):
        clients = list_top_clients(q="770020")
        assert len(clients) == 1
        assert clients[0]["phone"] == "+221770020000"

    def test_empty_when_no_orders(self, db):
        assert list_top_clients() == []
