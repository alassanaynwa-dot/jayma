"""Tests du modèle AbandonedCart — snapshot panier pour relances SMS."""
import pytest
from django.db import IntegrityError

from cart.models import AbandonedCart
from shops.models import Shop


@pytest.fixture
def shop(db, django_user_model):
    user = django_user_model.objects.create_user(
        username="m1", phone="+221770020001", email="m@x.sn",
        password="pwd", role=django_user_model.Role.MERCHANT,
    )
    return Shop.objects.create(
        owner=user, name="Shop", slug="shop-x",
        phone="+221770020001", city="Dakar",
        is_approved=True, is_active=True,
    )


@pytest.mark.django_db
class TestAbandonedCart:
    def test_create_with_snapshot_json(self, shop):
        cart = AbandonedCart.objects.create(
            shop=shop, client_phone="+221770100001", client_name="Aïssa",
            items_json=[
                {"product_id": 1, "name": "Robe", "unit_price": 15000, "quantity": 2},
                {"product_id": 2, "name": "Sac", "unit_price": 22000, "quantity": 1},
            ],
            total_xof=52000,
        )
        assert cart.pk is not None
        assert len(cart.items_json) == 2
        assert cart.total_xof == 52000
        assert cart.reminded_at is None
        assert cart.recovered_at is None

    def test_unique_together_shop_phone(self, shop):
        """Un seul AbandonedCart par couple (shop, client_phone)."""
        AbandonedCart.objects.create(
            shop=shop, client_phone="+221770100002",
            items_json=[], total_xof=0,
        )
        with pytest.raises(IntegrityError):
            AbandonedCart.objects.create(
                shop=shop, client_phone="+221770100002",
                items_json=[], total_xof=0,
            )

    def test_same_phone_different_shops_allowed(self, shop, django_user_model):
        """Le même phone peut avoir un cart dans 2 boutiques différentes."""
        user2 = django_user_model.objects.create_user(
            username="m2", phone="+221770020999", email="m2@x.sn",
            password="pwd", role=django_user_model.Role.MERCHANT,
        )
        shop2 = Shop.objects.create(
            owner=user2, name="Shop 2", slug="shop-x2",
            phone="+221770020999", city="Dakar",
            is_approved=True, is_active=True,
        )
        AbandonedCart.objects.create(shop=shop, client_phone="+221770100003", items_json=[], total_xof=0)
        AbandonedCart.objects.create(shop=shop2, client_phone="+221770100003", items_json=[], total_xof=0)
        assert AbandonedCart.objects.filter(client_phone="+221770100003").count() == 2

    def test_str_representation(self, shop):
        cart = AbandonedCart.objects.create(
            shop=shop, client_phone="+221770100004",
            items_json=[], total_xof=15000,
        )
        s = str(cart)
        assert "+221770100004" in s
        assert "15000" in s
        assert shop.slug in s
