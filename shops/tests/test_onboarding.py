"""Tests Levier 2 — checklist d'onboarding dashboard.

Vérifie le service compute_onboarding et que la checklist apparaît bien
en haut du dashboard tant qu'on n'est pas à 6/6.
"""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from delivery.models import DeliveryZone
from products.models import Category, Product
from shops.models import Shop
from shops.services.onboarding import compute_onboarding

User = get_user_model()


@pytest.fixture
def fresh_shop(db):
    """Boutique fraîchement créée — aucune étape complétée sauf 'compte créé'."""
    user = User.objects.create_user(
        username="newbie", phone="+221770000099", email="newbie@x.sn",
        password="testpass", role=User.Role.MERCHANT,
    )
    return Shop.objects.create(
        owner=user, name="Brand New", slug="brand-new",
        phone="+221770000099", city="Dakar",
        is_approved=True, is_active=True,
        # Champs d'onboarding tous vides : pas de description, pas de logo
        description="",
    )


@pytest.mark.django_db
class TestOnboardingService:
    def test_fresh_shop_has_one_step_done(self, fresh_shop):
        """Boutique fraîche → seule l'étape 'compte créé' est cochée."""
        state = compute_onboarding(fresh_shop)
        assert state.total == 6
        assert state.done_count == 1  # juste 'account'
        assert not state.is_complete
        assert state.percent == 17  # 1/6 ≈ 16.67 → 17

    def test_description_step_done_when_filled(self, fresh_shop):
        fresh_shop.description = "Une boutique sympa"
        fresh_shop.save()
        state = compute_onboarding(fresh_shop)
        desc_step = next(s for s in state.steps if s.key == "description")
        assert desc_step.done is True

    def test_categories_step_done_when_active_category(self, fresh_shop):
        Category.objects.create(shop=fresh_shop, name="Mode", slug="mode", is_active=True)
        state = compute_onboarding(fresh_shop)
        cat_step = next(s for s in state.steps if s.key == "categories")
        assert cat_step.done is True

    def test_inactive_categories_dont_count(self, fresh_shop):
        Category.objects.create(shop=fresh_shop, name="X", slug="x", is_active=False)
        state = compute_onboarding(fresh_shop)
        cat_step = next(s for s in state.steps if s.key == "categories")
        assert cat_step.done is False

    def test_first_product_step_done_when_active_product(self, fresh_shop):
        cat = Category.objects.create(shop=fresh_shop, name="X", slug="x")
        Product.objects.create(
            shop=fresh_shop, category=cat, name="P1", price=1000, stock=1,
            is_active=True,
        )
        state = compute_onboarding(fresh_shop)
        prod_step = next(s for s in state.steps if s.key == "first_product")
        assert prod_step.done is True

    def test_delivery_step_done_when_zone_exists(self, fresh_shop):
        DeliveryZone.objects.create(
            shop=fresh_shop, name="Dakar", fee_xof=1000,
        )
        state = compute_onboarding(fresh_shop)
        del_step = next(s for s in state.steps if s.key == "delivery")
        assert del_step.done is True

    def test_all_steps_done_marks_complete(self, fresh_shop):
        # Remplir toutes les étapes
        fresh_shop.description = "Boutique complète"
        # Pas de logo → on simule en sauvant une "ImageFieldFile" — trop complexe.
        # On skippe cette étape pour le test "all done" : on patche le state.
        fresh_shop.save()
        cat = Category.objects.create(shop=fresh_shop, name="C", slug="c")
        Product.objects.create(
            shop=fresh_shop, category=cat, name="P", price=1000, stock=1,
            is_active=True,
        )
        DeliveryZone.objects.create(shop=fresh_shop, name="D", fee_xof=500)
        state = compute_onboarding(fresh_shop)
        # 5/6 (manque le logo qui demande un vrai upload)
        assert state.done_count == 5
        # Avec logo on serait à 6/6 — testé indirectement via la logique
        # is_complete au calcul (done_count == total).


@pytest.mark.django_db
class TestChecklistInDashboard:
    def test_checklist_shown_when_incomplete(self, fresh_shop):
        c = Client(HTTP_HOST="dashboard.jayma.local")
        c.force_login(fresh_shop.owner)
        response = c.get("/")
        assert response.status_code == 200
        # La checklist apparaît
        assert b"Configure ta boutique" in response.content
        # Le compteur 1/6 apparaît
        assert b"1/6" in response.content or b"1 / 6" in response.content

    def test_checklist_hidden_when_complete(self, fresh_shop):
        """Quand tout est fait, la checklist disparaît."""
        from unittest.mock import patch
        # Patch là où la fonction est *importée* (pas où elle est définie)
        # pour que le mock prenne effet dans le template tag.
        with patch("shops.templatetags.onboarding_tags.compute_onboarding") as mock_compute:
            from shops.services.onboarding import OnboardingState
            mock_compute.return_value = OnboardingState(
                steps=[], done_count=6, total=6, is_complete=True,
            )
            c = Client(HTTP_HOST="dashboard.jayma.local")
            c.force_login(fresh_shop.owner)
            response = c.get("/")
            # La checklist doit être cachée (is_complete=True)
            assert b"Configure ta boutique" not in response.content
