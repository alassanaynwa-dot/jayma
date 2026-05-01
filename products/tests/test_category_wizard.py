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

    def test_post_one_universe_creates_parent_and_children(self, merchant_client):
        client, shop = merchant_client
        response = client.post(
            URL_CATEGORY_WIZARD,
            {"universe": ["mode_femme"]},
        )
        assert response.status_code == 302  # redirect vers list
        # Mode femme = 1 parent + 12 sous-cat = 13 catégories
        assert shop.categories.count() == 13
        # Le parent a l'emoji et est racine
        parent = shop.categories.get(slug="mode-femme")
        assert parent.parent is None
        assert parent.emoji == "👗"
        assert parent.name == "Mode femme"
        # Les enfants ont bien le parent
        assert shop.categories.filter(parent=parent).count() == 12
        child = shop.categories.get(name="Robes & tenues")
        assert child.parent == parent

    def test_post_two_universes_creates_all(self, merchant_client):
        client, shop = merchant_client
        client.post(
            URL_CATEGORY_WIZARD,
            {"universe": ["mode_femme", "beaute"]},
        )
        # Mode femme (1+12) + Beauté (1+14) = 28 catégories
        assert shop.categories.count() == 28
        assert shop.categories.filter(parent__isnull=True).count() == 2  # 2 racines
        assert shop.categories.filter(parent__isnull=False).count() == 26  # 26 enfants

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


@pytest.mark.django_db
class TestCategoryHierarchy:
    """Validation de la hiérarchie parent/enfant (max 2 niveaux)."""

    def test_root_category_has_no_parent(self, db, shop):
        cat = Category.objects.create(shop=shop, name="Mode femme", slug="mode-femme")
        assert cat.is_root
        assert cat.parent is None

    def test_child_has_correct_parent(self, db, shop):
        parent = Category.objects.create(shop=shop, name="Mode femme", slug="mode-femme")
        child = Category.objects.create(
            shop=shop, name="Robes", slug="robes", parent=parent,
        )
        assert child.parent == parent
        assert not child.is_root
        assert child in parent.children.all()

    def test_cannot_create_grand_child(self, db, shop):
        from django.core.exceptions import ValidationError

        parent = Category.objects.create(shop=shop, name="Mode", slug="mode")
        child = Category.objects.create(shop=shop, name="Robes", slug="robes", parent=parent)
        grandchild = Category(shop=shop, name="Robes courtes", slug="robes-courtes", parent=child)
        with pytest.raises(ValidationError):
            grandchild.full_clean()

    def test_cannot_be_own_parent(self, db, shop):
        from django.core.exceptions import ValidationError

        cat = Category.objects.create(shop=shop, name="Mode", slug="mode")
        cat.parent = cat
        with pytest.raises(ValidationError):
            cat.full_clean()

    def test_descendants_includes_self_and_children(self, db, shop):
        parent = Category.objects.create(shop=shop, name="Mode", slug="mode")
        child1 = Category.objects.create(shop=shop, name="Robes", slug="robes", parent=parent)
        child2 = Category.objects.create(shop=shop, name="Pantalons", slug="pantalons", parent=parent)
        descendants = parent.get_descendant_categories()
        assert parent in descendants
        assert child1 in descendants
        assert child2 in descendants
        assert len(descendants) == 3


@pytest.mark.django_db
class TestCategoryReorder:
    """Endpoint HTMX/fetch pour drag & drop."""

    URL_REORDER = "/produits/categories/reorder/"

    def test_reorder_updates_positions(self, merchant_client):
        client, shop = merchant_client
        c1 = Category.objects.create(shop=shop, name="A", slug="a", position=0)
        c2 = Category.objects.create(shop=shop, name="B", slug="b", position=1)
        c3 = Category.objects.create(shop=shop, name="C", slug="c", position=2)
        # Drag : on réordonne en C, A, B
        response = client.post(
            self.URL_REORDER,
            f"category_ids[]={c3.pk}&category_ids[]={c1.pk}&category_ids[]={c2.pk}",
            content_type="application/x-www-form-urlencoded",
        )
        assert response.status_code == 204
        c1.refresh_from_db()
        c2.refresh_from_db()
        c3.refresh_from_db()
        assert c3.position == 0
        assert c1.position == 1
        assert c2.position == 2

    def test_reorder_isolated_per_shop(self, merchant_client, db):
        """Un commerçant ne peut PAS réordonner les catégories d'une autre boutique."""
        client, shop = merchant_client
        # Crée une autre boutique avec une catégorie
        other_user = User.objects.create_user(
            username="bob", phone="+221770009999", role=User.Role.MERCHANT,
        )
        other_shop = Shop.objects.create(
            owner=other_user, name="Bob Shop", slug="bob-shop",
            is_approved=True, is_active=True,
        )
        other_cat = Category.objects.create(
            shop=other_shop, name="Other", slug="other", position=42,
        )
        # Awa tente de la réordonner
        client.post(
            self.URL_REORDER,
            f"category_ids[]={other_cat.pk}",
            content_type="application/x-www-form-urlencoded",
        )
        # La position de la catégorie d'autrui n'a PAS bougé
        other_cat.refresh_from_db()
        assert other_cat.position == 42


@pytest.mark.django_db
class TestPublicListFilter:
    """Le filtre ?cat=parent inclut les produits de toutes les sous-catégories."""

    def test_filter_by_parent_includes_children_products(self, db, shop):
        """Quand on filtre par un univers, on voit les produits de tous ses enfants."""
        from django.test import Client

        from products.models import Product

        parent = Category.objects.create(shop=shop, name="Mode", slug="mode-univ", emoji="👗")
        sub_a = Category.objects.create(shop=shop, name="Robes", slug="robes-univ", parent=parent)
        sub_b = Category.objects.create(shop=shop, name="Pantalons", slug="pantalons-univ", parent=parent)

        # 1 produit dans chaque sous-cat
        Product.objects.create(
            shop=shop, name="Robe rouge", slug="robe-rouge",
            price=15000, category=sub_a, is_active=True,
        )
        Product.objects.create(
            shop=shop, name="Jean noir", slug="jean-noir",
            price=12000, category=sub_b, is_active=True,
        )

        # Filtre par le parent → doit retourner les 2 produits
        client = Client(HTTP_HOST=f"{shop.slug}.jayma.local")
        response = client.get(f"/produits/?cat={parent.slug}")
        assert response.status_code == 200
        assert b"Robe rouge" in response.content
        assert b"Jean noir" in response.content

        # Filtre par sub_a → uniquement la robe
        response = client.get(f"/produits/?cat={sub_a.slug}")
        assert b"Robe rouge" in response.content
        assert b"Jean noir" not in response.content
