"""Tests du modèle Shop + ShopRequest."""
import pytest
from django.core.exceptions import ValidationError

from shops.models import Shop, slug_validator


class TestSlugValidator:
    def test_valid_slugs(self):
        for slug in ("abc", "chez-fatou", "abc-123", "mon-shop-123"):
            slug_validator(slug)  # ne doit pas lever

    def test_invalid_slugs(self):
        for slug in ("ab", "", "MAJUSCULE", "caractère_fr", "a" * 50):
            with pytest.raises(ValidationError):
                slug_validator(slug)


class TestShopModel:
    def test_str(self, shop):
        assert "testshop" in str(shop)
        assert shop.name in str(shop)

    def test_get_public_url_uses_settings_root(self, shop, settings):
        settings.JAYMA_ROOT_DOMAIN = "localhost"
        assert shop.get_public_url() == "https://testshop.localhost"
