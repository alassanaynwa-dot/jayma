"""Tests du service d'application des coupons."""
from datetime import timedelta

import pytest
from django.utils import timezone

from coupons.models import Coupon, CouponUsage
from coupons.services.application import try_apply_coupon


class TestPercentageCoupon:
    def test_applies_correctly(self, shop, coupon_10pct):
        result = try_apply_coupon(shop, "TESTCODE", 10000)
        assert result.coupon is not None
        assert result.discount_xof == 1000  # 10% de 10000
        assert result.error is None

    def test_case_insensitive(self, shop, coupon_10pct):
        result = try_apply_coupon(shop, "testcode", 10000)
        assert result.coupon is not None

    def test_below_min_order(self, shop, db):
        Coupon.objects.create(
            shop=shop, code="MIN5K", type=Coupon.Type.PERCENTAGE,
            value=20, min_order_xof=5000, is_active=True,
        )
        r = try_apply_coupon(shop, "MIN5K", 3000)
        assert r.coupon is None
        assert "minimum" in r.error.lower()

    def test_inactive(self, shop, coupon_10pct):
        coupon_10pct.is_active = False
        coupon_10pct.save()
        r = try_apply_coupon(shop, "TESTCODE", 10000)
        assert r.coupon is None

    def test_expired(self, shop, coupon_10pct):
        coupon_10pct.valid_until = timezone.now() - timedelta(days=1)
        coupon_10pct.save()
        r = try_apply_coupon(shop, "TESTCODE", 10000)
        assert r.coupon is None

    def test_not_yet_active(self, shop, coupon_10pct):
        coupon_10pct.valid_from = timezone.now() + timedelta(days=1)
        coupon_10pct.save()
        r = try_apply_coupon(shop, "TESTCODE", 10000)
        assert r.coupon is None

    def test_max_uses_reached(self, shop, coupon_10pct):
        coupon_10pct.max_uses = 3
        coupon_10pct.uses_count = 3
        coupon_10pct.save()
        r = try_apply_coupon(shop, "TESTCODE", 10000)
        assert r.coupon is None


class TestFixedCoupon:
    def test_fixed_discount(self, shop, db):
        Coupon.objects.create(
            shop=shop, code="MOINS2K",
            type=Coupon.Type.FIXED, value=2000, is_active=True,
        )
        r = try_apply_coupon(shop, "MOINS2K", 10000)
        assert r.discount_xof == 2000

    def test_capped_at_subtotal(self, shop, db):
        Coupon.objects.create(
            shop=shop, code="GIANT",
            type=Coupon.Type.FIXED, value=999999, is_active=True,
        )
        r = try_apply_coupon(shop, "GIANT", 5000)
        assert r.discount_xof == 5000  # borné au subtotal


class TestFreeshipCoupon:
    def test_freeship_is_flagged(self, shop, coupon_freeship):
        r = try_apply_coupon(shop, "FREESHIP", 10000)
        assert r.coupon is not None
        assert r.freeship is True
        assert r.discount_xof == 0  # freeship n'applique pas de discount subtotal

    def test_freeship_respects_min_order(self, shop, db):
        Coupon.objects.create(
            shop=shop, code="SHIP50K",
            type=Coupon.Type.FREESHIP, value=0, min_order_xof=50000,
            is_active=True,
        )
        r = try_apply_coupon(shop, "SHIP50K", 10000)
        assert r.coupon is None  # pas applicable


class TestOnePerCustomer:
    def test_blocks_second_use(self, shop, coupon_10pct, product, db):
        from orders.models import Order, OrderItem
        coupon_10pct.one_per_customer = True
        coupon_10pct.save()

        phone = "+221778889999"
        # Simule une utilisation précédente
        o = Order.objects.create(
            shop=shop, client_name="Test", client_phone=phone,
            client_address="x", client_city="Dakar",
            subtotal_xof=10000, total_xof=9000, discount_xof=1000,
            commission_rate=8, commission_xof=720, merchant_amount_xof=8280,
            payment_method=Order.PaymentMethod.CASH,
        )
        CouponUsage.objects.create(coupon=coupon_10pct, order=o, client_phone=phone, discount_xof=1000)

        # Tentative de 2e usage → refusée
        r = try_apply_coupon(shop, "TESTCODE", 10000, client_phone=phone)
        assert r.coupon is None
        assert "déjà utilisé" in r.error.lower()

    def test_allows_other_phones(self, shop, coupon_10pct):
        coupon_10pct.one_per_customer = True
        coupon_10pct.save()
        # Téléphone jamais utilisé → OK
        r = try_apply_coupon(shop, "TESTCODE", 10000, client_phone="+221770000000")
        assert r.coupon is not None


class TestUnknownCode:
    def test_unknown_code(self, shop):
        r = try_apply_coupon(shop, "JEXISTEPAS", 10000)
        assert r.coupon is None
        assert r.error is not None
