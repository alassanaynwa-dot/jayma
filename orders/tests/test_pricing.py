"""Tests du service pricing — calcul de commission."""
import pytest
from decimal import Decimal

from orders.services.pricing import compute_commission


class TestComputeCommission:
    def test_basic_8_percent(self):
        commission, merchant = compute_commission(10000, Decimal("8.00"))
        assert commission == 800
        assert merchant == 9200

    def test_zero_amount(self):
        assert compute_commission(0, Decimal("8.00")) == (0, 0)

    def test_floor_rounding(self):
        # 1234 * 8% = 98.72 → arrondi entier vers zéro = 98
        commission, merchant = compute_commission(1234, Decimal("8.00"))
        assert commission == 98
        assert merchant == 1136
        assert commission + merchant == 1234

    def test_custom_rate(self):
        commission, merchant = compute_commission(50000, Decimal("5.00"))
        assert commission == 2500
        assert merchant == 47500

    def test_sum_always_equals_total(self):
        """Invariant : commission + merchant == total, jamais de centimes perdus."""
        for amount in [1, 7, 99, 1000, 1234, 99999]:
            c, m = compute_commission(amount, Decimal("8.00"))
            assert c + m == amount
