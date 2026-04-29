"""Tests du matching zone <-> ville + suggestion livreur."""
import pytest

from delivery.models import Courier, DeliveryZone
from delivery.services.zones import (
    compute_delivery_fee,
    find_zone_for,
    suggest_courier_for_order,
)


class TestZoneMatching:
    def test_exact_match(self, shop, zone_dakar):
        assert find_zone_for(shop, "Plateau") == zone_dakar
        assert find_zone_for(shop, "Point E") == zone_dakar

    def test_case_insensitive(self, shop, zone_dakar):
        assert find_zone_for(shop, "PLATEAU") == zone_dakar
        assert find_zone_for(shop, "plateau") == zone_dakar

    def test_substring_match(self, shop, zone_dakar):
        # "Médina centre" doit matcher la zone qui contient "Médina"
        assert find_zone_for(shop, "Médina centre") == zone_dakar

    def test_no_match_returns_none(self, shop, zone_dakar):
        assert find_zone_for(shop, "Ziguinchor") is None

    def test_empty_city(self, shop, zone_dakar):
        assert find_zone_for(shop, "") is None
        assert find_zone_for(shop, None) is None

    def test_inactive_zone_not_matched(self, shop, zone_dakar):
        zone_dakar.is_active = False
        zone_dakar.save()
        assert find_zone_for(shop, "Plateau") is None


class TestComputeDeliveryFee:
    def test_matched_zone(self, shop, zone_dakar):
        fee, zone = compute_delivery_fee(shop, "Plateau")
        assert fee == 1500
        assert zone == zone_dakar

    def test_unmatched_zone_is_zero(self, shop, zone_dakar):
        fee, zone = compute_delivery_fee(shop, "Kaolack")
        assert fee == 0
        assert zone is None


class TestSuggestCourier:
    def test_courier_covering_zone(self, shop, courier, zone_dakar, product, db):
        from orders.models import Order
        o = Order.objects.create(
            shop=shop, client_name="x", client_phone="+221770000000",
            client_address="a", client_city="Plateau",
            subtotal_xof=1000, total_xof=1000, commission_rate=8,
            payment_method=Order.PaymentMethod.CASH,
        )
        suggested = suggest_courier_for_order(o)
        assert suggested == courier

    def test_no_zone_match_returns_any_active_courier(self, shop, courier, db):
        from orders.models import Order
        o = Order.objects.create(
            shop=shop, client_name="x", client_phone="+221770000000",
            client_address="a", client_city="VilleInconnue",
            subtotal_xof=1000, total_xof=1000, commission_rate=8,
            payment_method=Order.PaymentMethod.CASH,
        )
        # Fallback : premier livreur actif
        suggested = suggest_courier_for_order(o)
        assert suggested == courier
