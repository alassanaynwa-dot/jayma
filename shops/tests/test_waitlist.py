"""Tests Levier 1 — page boutique en préparation + waitlist signup.

Vérifie :
- Une boutique sans produit actif rend la page coming_soon (pas la home)
- Une boutique avec ≥1 produit actif rend la home normale
- Le POST /liste-attente/ crée un WaitlistSignup avec phone normalisé
- Doublon (même shop + même phone) silencieux (pas de 500)
- Phone invalide → message d'erreur, pas de signup
- SMS envoyé au commerçant (best-effort)
- Page dashboard /liste-attente/ liste les inscrits, accessible au seul commerçant
"""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from notifications.models import NotificationLog
from products.models import Category, Product
from shops.models import Shop, WaitlistSignup

User = get_user_model()


@pytest.fixture
def empty_shop(db):
    """Boutique sans aucun produit actif → doit afficher coming_soon."""
    user = User.objects.create_user(
        username="omar", phone="+221770000010", email="omar@x.sn",
        password="testpass", role=User.Role.MERCHANT,
    )
    return Shop.objects.create(
        owner=user, name="Chez Omar", slug="chez-omar",
        phone="+221770000010", city="Dakar",
        is_approved=True, is_active=True,
    )


@pytest.fixture
def filled_shop(db):
    """Boutique avec produit actif → doit afficher la home normale."""
    user = User.objects.create_user(
        username="awa", phone="+221770000020", email="awa@x.sn",
        password="testpass", role=User.Role.MERCHANT,
    )
    shop = Shop.objects.create(
        owner=user, name="Chez Awa", slug="chez-awa",
        phone="+221770000020", city="Dakar",
        is_approved=True, is_active=True,
    )
    cat = Category.objects.create(shop=shop, name="Mode", slug="mode")
    Product.objects.create(
        shop=shop, category=cat, name="Robe wax", price=15000, stock=5,
        is_active=True,
    )
    return shop


@pytest.mark.django_db
class TestComingSoonPage:
    def test_empty_shop_shows_coming_soon(self, empty_shop):
        c = Client(HTTP_HOST=f"{empty_shop.slug}.jayma.local")
        response = c.get("/")
        assert response.status_code == 200
        assert b"Boutique en pr" in response.content  # "Boutique en préparation"
        # Le form waitlist est présent
        assert b'name="phone"' in response.content
        assert b'action="/liste-attente/"' in response.content

    def test_filled_shop_shows_normal_home(self, filled_shop):
        c = Client(HTTP_HOST=f"{filled_shop.slug}.jayma.local")
        response = c.get("/")
        assert response.status_code == 200
        # Pas de coming_soon
        assert b"Boutique en pr" not in response.content
        # Home boutique présente
        assert b"Robe wax" in response.content or b"Nos cat" in response.content

    def test_inactive_products_dont_count(self, empty_shop):
        """Un produit existant mais is_active=False ne fait pas sortir du mode coming_soon."""
        cat = Category.objects.create(shop=empty_shop, name="X", slug="x")
        Product.objects.create(
            shop=empty_shop, category=cat, name="Brouillon", price=1000, stock=1,
            is_active=False,
        )
        c = Client(HTTP_HOST=f"{empty_shop.slug}.jayma.local")
        response = c.get("/")
        assert b"Boutique en pr" in response.content


@pytest.mark.django_db
class TestWaitlistSignup:
    def test_post_creates_signup_and_redirects(self, empty_shop):
        c = Client(HTTP_HOST=f"{empty_shop.slug}.jayma.local")
        response = c.post("/liste-attente/", {
            "phone": "+221770005555",
            "name": "Aïssatou",
            "email": "aissatou@x.sn",
        })
        assert response.status_code == 302
        assert "merci=1" in response["Location"]
        # Le signup existe
        signup = WaitlistSignup.objects.get(shop=empty_shop, phone="+221770005555")
        assert signup.name == "Aïssatou"
        assert signup.email == "aissatou@x.sn"

    def test_phone_normalized_to_e164(self, empty_shop):
        """Le phone doit être normalisé en +221XXXXXXXXX."""
        c = Client(HTTP_HOST=f"{empty_shop.slug}.jayma.local")
        c.post("/liste-attente/", {"phone": "770006666"})
        signup = WaitlistSignup.objects.get(shop=empty_shop)
        assert signup.phone == "+221770006666"

    def test_invalid_phone_no_signup(self, empty_shop):
        c = Client(HTTP_HOST=f"{empty_shop.slug}.jayma.local")
        response = c.post(
            "/liste-attente/",
            {"phone": "abc-not-phone"},
            follow=True,
        )
        assert response.status_code == 200
        assert WaitlistSignup.objects.filter(shop=empty_shop).count() == 0

    def test_duplicate_signup_silent(self, empty_shop):
        """Même phone soumis 2x → pas d'erreur 500, et un seul signup en BDD."""
        c = Client(HTTP_HOST=f"{empty_shop.slug}.jayma.local")
        c.post("/liste-attente/", {"phone": "+221770007777"})
        # Deuxième POST identique
        response = c.post("/liste-attente/", {"phone": "+221770007777"})
        assert response.status_code == 302
        assert WaitlistSignup.objects.filter(
            shop=empty_shop, phone="+221770007777",
        ).count() == 1

    def test_sms_sent_to_merchant(self, empty_shop):
        """Le commerçant reçoit un SMS quand quelqu'un s'inscrit."""
        before = NotificationLog.objects.count()
        c = Client(HTTP_HOST=f"{empty_shop.slug}.jayma.local")
        c.post("/liste-attente/", {"phone": "+221770008888", "name": "Fatou"})
        # Au moins un nouveau log SMS pour le commerçant
        new_logs = NotificationLog.objects.order_by("-created_at")[:1]
        assert NotificationLog.objects.count() > before
        log = new_logs[0]
        assert log.recipient == empty_shop.owner.phone
        assert "Fatou" in log.body
        assert empty_shop.name in log.body

    def test_signup_count_displayed_when_3_or_more(self, empty_shop):
        for i in range(3):
            WaitlistSignup.objects.create(
                shop=empty_shop, phone=f"+22177000{i:04d}",
            )
        c = Client(HTTP_HOST=f"{empty_shop.slug}.jayma.local")
        response = c.get("/")
        # Le compteur "3 personnes attendent déjà" doit apparaître
        assert b"3" in response.content
        assert b"attendent d" in response.content

    def test_thank_you_state_after_redirect(self, empty_shop):
        c = Client(HTTP_HOST=f"{empty_shop.slug}.jayma.local")
        response = c.get("/?merci=1")
        # État de confirmation présent
        assert b"Merci" in response.content


@pytest.mark.django_db
class TestWaitlistDashboard:
    def test_dashboard_shows_signups_to_owner(self, empty_shop):
        WaitlistSignup.objects.create(
            shop=empty_shop, phone="+221770009999", name="TestPersonne",
        )
        c = Client(HTTP_HOST="dashboard.jayma.local")
        c.force_login(empty_shop.owner)
        response = c.get("/parametres/liste-attente/")
        assert response.status_code == 200
        assert b"TestPersonne" in response.content
        assert b"+221770009999" in response.content

    def test_dashboard_inaccessible_to_other_merchant(self, empty_shop, filled_shop):
        """Un autre commerçant ne voit pas la waitlist d'omar."""
        WaitlistSignup.objects.create(
            shop=empty_shop, phone="+221770009999", name="SecretPersonne",
        )
        c = Client(HTTP_HOST="dashboard.jayma.local")
        c.force_login(filled_shop.owner)  # awa, pas omar
        response = c.get("/parametres/liste-attente/")
        # awa ne doit pas voir le signup d'omar
        assert b"SecretPersonne" not in response.content
