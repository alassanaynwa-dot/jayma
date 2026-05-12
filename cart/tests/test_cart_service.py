"""Tests du service panier (Cart) — stockage session, totaux, multi-boutique.

L'app cart n'avait aucun test avant ces ajouts. Le panier est stocké en
session côté client (pas en BDD pour le panier actif), et on snapshotte
en BDD via AbandonedCart pour les relances.
"""
import pytest
from django.test import RequestFactory

from cart.services.cart import CART_SESSION_KEY, Cart
from products.models import Product
from shops.models import Shop


@pytest.fixture
def request_with_session(db):
    """RequestFactory + vraie SessionStore Django (en mémoire pour tests)."""
    from django.contrib.sessions.backends.db import SessionStore
    rf = RequestFactory()
    request = rf.get("/")
    request.session = SessionStore()
    request.session.create()
    return request


@pytest.fixture
def shop_a(db, django_user_model):
    user = django_user_model.objects.create_user(
        username="m_a", phone="+221770010001", email="a@x.sn",
        password="pwd", role=django_user_model.Role.MERCHANT,
    )
    return Shop.objects.create(
        owner=user, name="Shop A", slug="shop-a",
        phone="+221770010001", city="Dakar",
        is_approved=True, is_active=True,
    )


@pytest.fixture
def shop_b(db, django_user_model):
    user = django_user_model.objects.create_user(
        username="m_b", phone="+221770010002", email="b@x.sn",
        password="pwd", role=django_user_model.Role.MERCHANT,
    )
    return Shop.objects.create(
        owner=user, name="Shop B", slug="shop-b",
        phone="+221770010002", city="Dakar",
        is_approved=True, is_active=True,
    )


@pytest.fixture
def product_a(shop_a):
    return Product.objects.create(
        shop=shop_a, name="Robe A", price=15000, stock=10, is_active=True,
    )


@pytest.fixture
def product_a2(shop_a):
    return Product.objects.create(
        shop=shop_a, name="Sac A", price=8000, stock=5, is_active=True,
    )


@pytest.fixture
def product_b(shop_b):
    return Product.objects.create(
        shop=shop_b, name="Bijou B", price=22000, stock=3, is_active=True,
    )


@pytest.mark.django_db
class TestCartBasics:
    def test_empty_cart_initial(self, request_with_session):
        cart = Cart(request_with_session)
        assert cart.item_count == 0
        assert cart.total_xof == 0
        assert cart.cart["shop_id"] is None
        assert cart.cart["items"] == {}

    def test_add_product_creates_entry(self, request_with_session, product_a):
        cart = Cart(request_with_session)
        cart.add(product_a, quantity=2)
        assert str(product_a.pk) in cart.cart["items"]
        item = cart.cart["items"][str(product_a.pk)]
        assert item["quantity"] == 2
        assert item["unit_price"] == 15000
        assert item["name"] == "Robe A"

    def test_add_same_product_twice_increments(self, request_with_session, product_a):
        cart = Cart(request_with_session)
        cart.add(product_a, quantity=2)
        cart.add(product_a, quantity=3)
        assert cart.cart["items"][str(product_a.pk)]["quantity"] == 5

    def test_total_xof_sums_correctly(self, request_with_session, product_a, product_a2):
        cart = Cart(request_with_session)
        cart.add(product_a, quantity=2)   # 2 × 15000 = 30000
        cart.add(product_a2, quantity=1)  # 1 × 8000 = 8000
        assert cart.total_xof == 38000

    def test_item_count_sums_quantities(self, request_with_session, product_a, product_a2):
        cart = Cart(request_with_session)
        cart.add(product_a, quantity=2)
        cart.add(product_a2, quantity=3)
        assert cart.item_count == 5
        assert len(cart) == 5

    def test_remove_clears_item(self, request_with_session, product_a, product_a2):
        cart = Cart(request_with_session)
        cart.add(product_a)
        cart.add(product_a2)
        cart.remove(product_a.pk)
        assert str(product_a.pk) not in cart.cart["items"]
        assert str(product_a2.pk) in cart.cart["items"]

    def test_remove_last_item_resets_shop_id(self, request_with_session, product_a):
        cart = Cart(request_with_session)
        cart.add(product_a)
        cart.remove(product_a.pk)
        assert cart.cart["shop_id"] is None

    def test_clear_empties_cart(self, request_with_session, product_a):
        cart = Cart(request_with_session)
        cart.add(product_a, quantity=3)
        cart.clear()
        assert cart.item_count == 0
        assert cart.total_xof == 0
        assert cart.cart["shop_id"] is None


@pytest.mark.django_db
class TestCartShopIsolation:
    """Un panier = une boutique. Ajouter un produit d'une autre boutique reset."""

    def test_first_add_sets_shop_id(self, request_with_session, product_a):
        cart = Cart(request_with_session)
        cart.add(product_a)
        assert cart.cart["shop_id"] == product_a.shop_id

    def test_adding_product_from_other_shop_resets_cart(
        self, request_with_session, product_a, product_b,
    ):
        cart = Cart(request_with_session)
        cart.add(product_a, quantity=3)
        assert cart.item_count == 3

        # Ajout d'un produit de shop_b → ancien panier wipe, nouveau panier
        cart.add(product_b, quantity=1)
        assert cart.cart["shop_id"] == product_b.shop_id
        assert str(product_a.pk) not in cart.cart["items"]
        assert cart.item_count == 1


@pytest.mark.django_db
class TestCartPersistsToSession:
    def test_save_writes_to_session_key(self, request_with_session, product_a):
        cart = Cart(request_with_session)
        cart.add(product_a)
        # Vérifie que la session contient bien notre cart sous la bonne clé
        assert CART_SESSION_KEY in request_with_session.session
        assert request_with_session.session[CART_SESSION_KEY] == cart.cart

    def test_new_cart_instance_reads_existing_session(
        self, request_with_session, product_a,
    ):
        c1 = Cart(request_with_session)
        c1.add(product_a, quantity=4)
        # Nouvelle instance Cart sur la même request → doit retrouver l'état
        c2 = Cart(request_with_session)
        assert c2.item_count == 4
