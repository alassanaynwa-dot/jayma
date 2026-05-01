"""Tests du wizard d'idées produits (approche B : pas de produit créé)."""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from products.data.product_suggestions import (
    PRODUCT_SUGGESTIONS,
    get_suggestion_by_key,
    suggestions_by_universe,
)
from products.models import Category, Product
from shops.models import Shop

User = get_user_model()

DASHBOARD_HOST = "dashboard.jayma.local"
URL_SUGGESTIONS = "/produits/idees/"
URL_CREATE = "/produits/ajouter/"


@pytest.fixture
def merchant_client(db):
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
class TestSuggestionsCatalog:
    def test_at_least_30_suggestions(self):
        assert len(PRODUCT_SUGGESTIONS) >= 30

    def test_each_suggestion_has_required_fields(self):
        required = {"key", "name", "universe_key", "suggested_price", "description"}
        for s in PRODUCT_SUGGESTIONS:
            assert required.issubset(set(s.keys()))
            assert isinstance(s["suggested_price"], int) and s["suggested_price"] > 0

    def test_keys_are_unique(self):
        keys = [s["key"] for s in PRODUCT_SUGGESTIONS]
        assert len(keys) == len(set(keys))

    def test_get_by_key(self):
        first = PRODUCT_SUGGESTIONS[0]
        assert get_suggestion_by_key(first["key"]) == first
        assert get_suggestion_by_key("nope-not-existing") is None

    def test_grouped_by_universe(self):
        by_uni = suggestions_by_universe()
        assert "mode_femme" in by_uni
        assert all(s["universe_key"] == "mode_femme" for s in by_uni["mode_femme"])


@pytest.mark.django_db
class TestSuggestionsView:
    def test_get_displays_all(self, merchant_client):
        client, shop = merchant_client
        response = client.get(URL_SUGGESTIONS)
        assert response.status_code == 200
        assert b"Inspiration" in response.content
        # Les noms de quelques suggestions doivent être présents
        assert b"Boubou" in response.content

    def test_filter_by_universe(self, merchant_client):
        client, shop = merchant_client
        response = client.get(URL_SUGGESTIONS + "?u=mode_femme")
        assert response.status_code == 200
        # Une suggestion typique mode femme
        assert b"Boubou brod" in response.content
        # Pas une suggestion d'un autre univers (ex : Powerbank en électronique)
        assert b"Powerbank" not in response.content


@pytest.mark.django_db
class TestProductCreatePrefill:
    """Quand on arrive sur create avec ?suggestion=key, le form doit être pré-rempli."""

    def test_suggestion_prefills_form(self, merchant_client):
        client, shop = merchant_client
        # Récupère la 1re suggestion pour trouver une key valide
        sg = PRODUCT_SUGGESTIONS[0]
        response = client.get(f"{URL_CREATE}?suggestion={sg['key']}")
        assert response.status_code == 200
        # Le nom + description suggérés doivent être dans la page (champs initial)
        assert sg["name"].encode() in response.content
        assert str(sg["suggested_price"]).encode() in response.content

    def test_unknown_suggestion_does_not_crash(self, merchant_client):
        client, shop = merchant_client
        response = client.get(f"{URL_CREATE}?suggestion=does-not-exist")
        # Le form s'affiche normalement (vide), pas de 500
        assert response.status_code == 200

    def test_suggestion_preselects_category_if_imported(self, merchant_client):
        """Si la boutique a importé l'univers via wizard, la catégorie est pré-sélectionnée."""
        client, shop = merchant_client
        # Crée la catégorie correspondante en BDD pour cette boutique
        sg = next(s for s in PRODUCT_SUGGESTIONS if s.get("suggested_category_slug"))
        cat = Category.objects.create(
            shop=shop, name="Cat test", slug=sg["suggested_category_slug"],
        )
        response = client.get(f"{URL_CREATE}?suggestion={sg['key']}")
        assert response.status_code == 200
        # L'option <option value="..." selected> doit être présente
        assert f'value="{cat.pk}" selected'.encode() in response.content

    def test_suggestion_does_not_create_product(self, merchant_client):
        """Visiter create avec ?suggestion= ne crée AUCUN produit en BDD (approche B)."""
        client, shop = merchant_client
        sg = PRODUCT_SUGGESTIONS[0]
        client.get(f"{URL_CREATE}?suggestion={sg['key']}")
        # Aucun produit créé tant que le commerçant n'a pas POST le form
        assert Product.objects.filter(shop=shop).count() == 0
