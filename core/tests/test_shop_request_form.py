"""Tests du calcul automatique du slug à partir du nom de boutique."""
import pytest

from core.forms import ShopRequestForm
from shops.models import Shop, ShopRequest


def _form_data(shop_name: str, **overrides) -> dict:
    """Données minimales valides pour ShopRequestForm."""
    base = {
        "full_name": "Awa Diop",
        "email": "awa@exemple.sn",
        "phone": "+221771234567",
        "city": "Dakar",
        "shop_name": shop_name,
        "product_category": "Vêtements",
        "description": "",
        "terms_accepted": True,
    }
    base.update(overrides)
    return base


@pytest.mark.django_db
class TestAutoSlugFromShopName:
    """Le slug est dérivé du shop_name automatiquement, plus de champ séparé."""

    def test_basic_slug_from_name(self):
        form = ShopRequestForm(data=_form_data("Chez Awa"))
        assert form.is_valid(), form.errors
        sr = form.save()
        assert sr.desired_slug == "chez-awa"

    def test_accents_removed(self):
        form = ShopRequestForm(data=_form_data("Boutique Élégance"))
        assert form.is_valid(), form.errors
        sr = form.save()
        assert sr.desired_slug == "boutique-elegance"

    def test_special_chars_stripped(self):
        form = ShopRequestForm(data=_form_data("Mode & Style !"))
        assert form.is_valid(), form.errors
        sr = form.save()
        assert sr.desired_slug == "mode-style"

    def test_collision_with_existing_shop_appends_suffix(self, db):
        # Shop préexistante avec slug "chez-awa"
        from django.contrib.auth import get_user_model
        User = get_user_model()
        owner = User.objects.create_user(username="awa1", phone="+221770000001")
        Shop.objects.create(
            owner=owner, name="Chez Awa Existante", slug="chez-awa",
            is_approved=True, is_active=True,
        )

        form = ShopRequestForm(data=_form_data("Chez Awa"))
        assert form.is_valid(), form.errors
        sr = form.save()
        assert sr.desired_slug == "chez-awa-2"

    def test_collision_with_pending_request_appends_suffix(self):
        ShopRequest.objects.create(
            full_name="Aïssatou", email="ais@x.sn", phone="+221771112233",
            city="Dakar", shop_name="Chez Awa", desired_slug="chez-awa",
            status=ShopRequest.Status.PENDING,
        )

        form = ShopRequestForm(data=_form_data("Chez Awa", email="awa2@x.sn"))
        assert form.is_valid(), form.errors
        sr = form.save()
        assert sr.desired_slug == "chez-awa-2"

    def test_too_short_name_rejected(self):
        form = ShopRequestForm(data=_form_data("A"))
        assert not form.is_valid()
        assert "shop_name" in form.errors

    def test_unsluggable_name_rejected(self):
        # Nom uniquement composé de caractères non-slug-safe
        form = ShopRequestForm(data=_form_data("@@@"))
        assert not form.is_valid()
        assert "shop_name" in form.errors

    def test_reserved_subdomain_rejected(self):
        form = ShopRequestForm(data=_form_data("admin"))
        assert not form.is_valid()
        assert "shop_name" in form.errors

    def test_long_name_truncated_to_40_chars(self):
        # 60 caractères → slug doit être tronqué à 40
        long_name = "Boutique super extraordinaire de vetements et accessoires"
        form = ShopRequestForm(data=_form_data(long_name))
        assert form.is_valid(), form.errors
        sr = form.save()
        assert len(sr.desired_slug) <= 40
        assert sr.desired_slug.startswith("boutique-super-extraordinaire")
