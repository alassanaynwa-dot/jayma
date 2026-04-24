"""Fixtures globales pytest pour les tests Jappesi."""
import pytest
from django.contrib.auth import get_user_model

from shops.models import Shop
from products.models import Category, PackItem, Product
from delivery.models import Courier, DeliveryZone
from coupons.models import Coupon


User = get_user_model()


@pytest.fixture
def merchant_user(db):
    return User.objects.create_user(
        username="test_merchant",
        email="merchant@test.sn",
        password="pw",
        role=User.Role.MERCHANT,
        phone="+221771112233",
        city="Dakar",
        first_name="Test",
    )


@pytest.fixture
def shop(db, merchant_user):
    return Shop.objects.create(
        owner=merchant_user,
        name="Test Shop",
        slug="testshop",
        phone="+221771112233",
        city="Dakar",
        is_approved=True,
        is_active=True,
        commission_rate=8,
    )


@pytest.fixture
def category(db, shop):
    return Category.objects.create(shop=shop, name="Cat", slug="cat")


@pytest.fixture
def product(db, shop, category):
    return Product.objects.create(
        shop=shop, category=category,
        name="Produit A", slug="produit-a",
        price=10000, stock=10,
    )


@pytest.fixture
def product2(db, shop, category):
    return Product.objects.create(
        shop=shop, category=category,
        name="Produit B", slug="produit-b",
        price=5000, stock=20,
    )


@pytest.fixture
def pack(db, shop, product, product2):
    """Pack qui combine product + product2."""
    p = Product.objects.create(
        shop=shop, kind=Product.Kind.PACK,
        name="Pack AB", slug="pack-ab",
        price=12000, compare_at_price=15000,
        track_stock=False,
    )
    PackItem.objects.create(pack=p, item=product, quantity=1)
    PackItem.objects.create(pack=p, item=product2, quantity=1)
    return p


@pytest.fixture
def zone_dakar(db, shop):
    return DeliveryZone.objects.create(
        shop=shop, name="Dakar centre",
        cities="Plateau, Médina, Point E",
        fee_xof=1500,
    )


@pytest.fixture
def courier(db, shop, zone_dakar):
    c = Courier.objects.create(
        shop=shop, name="Modou Test", phone="+221775554433",
        vehicle=Courier.Vehicle.MOTO,
    )
    c.covered_zones.add(zone_dakar)
    return c


@pytest.fixture
def coupon_10pct(db, shop):
    return Coupon.objects.create(
        shop=shop, code="TESTCODE",
        type=Coupon.Type.PERCENTAGE, value=10,
        is_active=True,
    )


@pytest.fixture
def coupon_freeship(db, shop):
    return Coupon.objects.create(
        shop=shop, code="FREESHIP",
        type=Coupon.Type.FREESHIP, value=0,
        is_active=True,
    )
