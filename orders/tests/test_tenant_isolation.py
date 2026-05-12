"""Tests cross-tenant : un commerçant ne doit pas accéder aux données
d'une autre boutique. Critique pour la confidentialité multi-tenant.

Avant ces tests, seul 1 test cross-tenant existait (waitlist). On couvre
ici les vues critiques côté dashboard commerçant : commandes, produits,
clients, livraison.
"""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from orders.models import Order
from products.models import Product
from shops.models import Shop

User = get_user_model()
DASHBOARD_HOST = "dashboard.jayma.local"


@pytest.fixture
def merchant_a(db):
    user = User.objects.create_user(
        username="merch_a", phone="+221770000001", email="a@x.sn",
        password="pwd", role=User.Role.MERCHANT,
    )
    shop = Shop.objects.create(
        owner=user, name="Shop A", slug="shop-a",
        phone="+221770000001", city="Dakar",
        is_approved=True, is_active=True,
    )
    return user, shop


@pytest.fixture
def merchant_b(db):
    user = User.objects.create_user(
        username="merch_b", phone="+221770000002", email="b@x.sn",
        password="pwd", role=User.Role.MERCHANT,
    )
    shop = Shop.objects.create(
        owner=user, name="Shop B", slug="shop-b",
        phone="+221770000002", city="Dakar",
        is_approved=True, is_active=True,
    )
    return user, shop


def _make_order(shop, ref_suffix="X1"):
    return Order.objects.create(
        shop=shop,
        client_name=f"Client {ref_suffix}",
        client_phone="+221770000100",
        client_address="rue", client_city="Dakar",
        subtotal_xof=10000, total_xof=10000,
        commission_rate=Decimal("8.00"),
        commission_xof=800, merchant_amount_xof=9200,
        payment_method=Order.PaymentMethod.CASH,
        status=Order.Status.PENDING,
    )


@pytest.mark.django_db
class TestOrderIsolation:
    def test_merchant_a_cannot_see_merchant_b_orders_in_list(
        self, merchant_a, merchant_b,
    ):
        """Liste des commandes : le commerçant A ne voit que les siennes."""
        user_a, shop_a = merchant_a
        user_b, shop_b = merchant_b
        order_b = _make_order(shop_b, ref_suffix="B-Secret")

        c = Client(HTTP_HOST=DASHBOARD_HOST)
        c.force_login(user_a)
        response = c.get("/commandes/")
        assert response.status_code == 200
        # La commande de B ne doit pas apparaître dans la page de A
        assert b"B-Secret" not in response.content
        assert order_b.reference.encode() not in response.content

    def test_merchant_a_cannot_view_order_detail_of_b(
        self, merchant_a, merchant_b,
    ):
        """Accès direct à /commandes/<ref> d'un autre commerçant → 404."""
        user_a, _ = merchant_a
        _, shop_b = merchant_b
        order_b = _make_order(shop_b, ref_suffix="B-Hidden")

        c = Client(HTTP_HOST=DASHBOARD_HOST)
        c.force_login(user_a)
        response = c.get(f"/commandes/{order_b.reference}/")
        # 404 attendu : l'order n'existe pas "pour ce merchant"
        assert response.status_code == 404


@pytest.mark.django_db
class TestProductIsolation:
    def test_merchant_a_cannot_see_b_products_in_list(
        self, merchant_a, merchant_b,
    ):
        user_a, _ = merchant_a
        _, shop_b = merchant_b
        Product.objects.create(
            shop=shop_b, name="Produit Secret B", price=99999, stock=1,
            is_active=True,
        )

        c = Client(HTTP_HOST=DASHBOARD_HOST)
        c.force_login(user_a)
        response = c.get("/produits/")
        assert response.status_code == 200
        assert b"Produit Secret B" not in response.content

    def test_merchant_a_cannot_edit_b_product(
        self, merchant_a, merchant_b,
    ):
        """Accès direct au form d'édition d'un produit d'un autre → 404."""
        user_a, _ = merchant_a
        _, shop_b = merchant_b
        prod_b = Product.objects.create(
            shop=shop_b, name="Produit B", price=10000, stock=1,
            is_active=True,
        )
        c = Client(HTTP_HOST=DASHBOARD_HOST)
        c.force_login(user_a)
        response = c.get(f"/produits/{prod_b.pk}/modifier/")
        assert response.status_code == 404

    def test_anonymous_cannot_access_dashboard_products(self):
        c = Client(HTTP_HOST=DASHBOARD_HOST)
        response = c.get("/produits/")
        assert response.status_code in (301, 302)
        assert "/login" in response["Location"] or "comptes" in response["Location"]


@pytest.mark.django_db
class TestClientsIsolation:
    def test_merchant_a_cannot_see_b_clients(
        self, merchant_a, merchant_b,
    ):
        """La page clients dashboard montre les acheteurs de SA boutique."""
        user_a, _ = merchant_a
        _, shop_b = merchant_b
        # Client unique chez B
        _make_order(shop_b, ref_suffix="B")
        # On modifie le phone pour qu'on puisse vérifier l'isolation
        Order.objects.filter(shop=shop_b).update(client_phone="+221770099999")

        c = Client(HTTP_HOST=DASHBOARD_HOST)
        c.force_login(user_a)
        response = c.get("/clients/")
        assert response.status_code == 200
        # Le numéro client de B ne doit pas apparaître chez A
        assert b"+221770099999" not in response.content
