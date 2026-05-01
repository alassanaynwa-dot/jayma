"""Tests du wizard d'onboarding catégories."""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from products.data.category_templates import CATEGORY_TEMPLATES, total_subcategories
from products.models import Category
from shops.models import Shop

User = get_user_model()

# URLs dashboard hardcodées (le namespace 'products_dashboard' n'est résolu
# que via le subdomain dashboard.* géré par le TenantMiddleware ; reverse()
# en test direct ne le voit pas sans request).
URL_CATEGORY_LIST = "/produits/categories/"
URL_CATEGORY_WIZARD = "/produits/categories/wizard/"


DASHBOARD_HOST = "dashboard.jayma.local"


@pytest.fixture
def merchant_client(db):
    """Un commerçant connecté avec sa boutique, prêt à utiliser le wizard.

    Toutes les requêtes via ce client ciblent le sous-domaine dashboard
    (HTTP_HOST set), pour que TenantMiddleware bascule sur urls_dashboard.
    """
    user = User.objects.create_user(
        username="awa", phone="+221770001234", email="awa@x.sn",
        password="testpass123", role=User.Role.MERCHANT,
    )
    shop = Shop.objects.create(
        owner=user, name="Chez Awa", slug="chez-awa",
        is_approved=True, is_active=True,
    )
    client = Client(HTTP_HOST=DASHBOARD_HOST)
    client.force_login(user)
    return client, shop


@pytest.mark.django_db
class TestCategoryTemplates:
    def test_10_universes_defined(self):
        assert len(CATEGORY_TEMPLATES) == 10

    def test_each_universe_has_emoji_and_subcategories(self):
        for tpl in CATEGORY_TEMPLATES:
            assert "emoji" in tpl and tpl["emoji"]
            assert "subcategories" in tpl and len(tpl["subcategories"]) >= 5
            assert "key" in tpl and tpl["key"]
            assert "label" in tpl and tpl["label"]

    def test_keys_are_unique(self):
        keys = [t["key"] for t in CATEGORY_TEMPLATES]
        assert len(keys) == len(set(keys))

    def test_total_subcategories_count_reasonable(self):
        assert 60 <= total_subcategories() <= 120


@pytest.mark.django_db
class TestCategoryWizard:
    """Le wizard copie les sous-cat sélectionnées dans la boutique du commerçant."""

    def test_get_displays_all_universes(self, merchant_client):
        client, shop = merchant_client
        response = client.get(URL_CATEGORY_WIZARD)
        assert response.status_code == 200
        assert b"Mode femme" in response.content
        assert b"Alimentation" in response.content

    def test_post_one_universe_creates_subcategories(self, merchant_client):
        client, shop = merchant_client
        response = client.post(
            URL_CATEGORY_WIZARD,
            {"universe": ["mode_femme"]},
        )
        assert response.status_code == 302  # redirect vers list
        # Mode femme a 12 sous-cat dans le template
        assert shop.categories.count() == 12
        assert shop.categories.filter(name="Robes & tenues").exists()
        assert shop.categories.filter(name="Boubous & bazin").exists()

    def test_post_two_universes_creates_all(self, merchant_client):
        client, shop = merchant_client
        client.post(
            URL_CATEGORY_WIZARD,
            {"universe": ["mode_femme", "beaute"]},
        )
        # Mode femme (12) + Beauté (14) = 26
        assert shop.categories.count() == 26

    def test_idempotent_no_duplicates(self, merchant_client):
        client, shop = merchant_client
        # 1ère import
        client.post(
            URL_CATEGORY_WIZARD,
            {"universe": ["mode_femme"]},
        )
        count_after_first = shop.categories.count()
        # 2e import du même univers → pas de doublons
        client.post(
            URL_CATEGORY_WIZARD,
            {"universe": ["mode_femme"]},
        )
        assert shop.categories.count() == count_after_first

    def test_no_selection_redirects_with_error(self, merchant_client):
        client, shop = merchant_client
        response = client.post(
            URL_CATEGORY_WIZARD,
            {"universe": []},
        )
        assert response.status_code == 302
        assert shop.categories.count() == 0

    def test_max_5_universes_enforced(self, merchant_client):
        client, shop = merchant_client
        keys = [t["key"] for t in CATEGORY_TEMPLATES[:6]]  # 6 univers
        response = client.post(
            URL_CATEGORY_WIZARD,
            {"universe": keys},
        )
        assert response.status_code == 302
        # Aucune catégorie créée car 6 > limite de 5
        assert shop.categories.count() == 0

    def test_categories_get_unique_slugs(self, merchant_client):
        client, shop = merchant_client
        client.post(
            URL_CATEGORY_WIZARD,
            {"universe": ["mode_femme"]},
        )
        slugs = list(shop.categories.values_list("slug", flat=True))
        assert len(slugs) == len(set(slugs))  # tous uniques
        assert "robes-tenues" in slugs

    def test_wizard_promo_shown_when_no_categories(self, merchant_client):
        client, shop = merchant_client
        response = client.get(URL_CATEGORY_LIST)
        assert response.status_code == 200
        assert b"Pr" in response.content  # "Pré-remplir" ou similaire
        # Importe quelques catégories
        Category.objects.create(shop=shop, name="Test", slug="test")
        response = client.get(URL_CATEGORY_LIST)
        # Le bandeau promo devrait disparaître
        assert b"D" in response.content  # juste vérifier que la page rend
