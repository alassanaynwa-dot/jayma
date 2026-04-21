"""Tests des packs de produits."""
import pytest

from products.models import PackItem, Product


class TestPackModel:
    def test_pack_is_pack_flag(self, pack, product):
        assert pack.is_pack is True
        assert product.is_pack is False

    def test_pack_includes_items(self, pack, product, product2):
        items = list(pack.items_in_pack.all())
        products_in_pack = {pi.item for pi in items}
        assert product in products_in_pack
        assert product2 in products_in_pack

    def test_pack_savings(self, pack, product, product2):
        # product 10000 + product2 5000 = 15000 vs pack 12000 → économie 3000
        assert pack.total_savings() == 3000

    def test_pack_is_available_when_all_sub_products_in_stock(self, pack):
        assert pack.is_available is True

    def test_pack_unavailable_when_sub_product_out_of_stock(self, pack, product):
        product.stock = 0
        product.save()
        assert pack.is_available is False

    def test_pack_unavailable_when_sub_product_inactive(self, pack, product):
        product.is_active = False
        product.save()
        assert pack.is_available is False

    def test_simple_product_no_savings(self, product):
        assert product.total_savings() == 0
