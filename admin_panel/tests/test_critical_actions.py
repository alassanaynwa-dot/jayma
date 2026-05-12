"""Tests des actions admin qui changent l'état production.

Ces actions étaient à 26% de couverture (admin_panel/views.py 449 LOC).
Elles modifient des données critiques (approval boutique, commission,
réglages plateforme, kill-switch SMS) — un bug ici se voit immédiatement
en prod. Coverage cible : 100% sur ces 6 vues.
"""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from admin_panel.models import AdminAction
from commissions.models import Commission
from core.models import PlatformSettings
from orders.models import Order
from shops.models import Shop, ShopRequest

User = get_user_model()
ADMIN_HOST = "admin.jayma.local"


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username="admin1", phone="+221770000001", email="admin@x.sn",
        password="adminpass", role=User.Role.ADMIN,
    )


@pytest.fixture
def admin_client(admin_user):
    c = Client(HTTP_HOST=ADMIN_HOST)
    c.force_login(admin_user)
    return c


@pytest.fixture
def shop(db):
    user = User.objects.create_user(
        username="merch1", phone="+221770000010", email="m@x.sn",
        password="pwd", role=User.Role.MERCHANT,
    )
    return Shop.objects.create(
        owner=user, name="Test Shop", slug="test-shop",
        phone="+221770000010", city="Dakar",
        is_approved=True, is_active=True,
        commission_rate=Decimal("8.00"),
    )


@pytest.fixture
def shop_request(db):
    return ShopRequest.objects.create(
        shop_name="Future Boutique",
        full_name="Fatou Sow",
        email="fatou@x.sn",
        phone="+221770000020",
        desired_slug="future-boutique",
        city="Thiès",
        status=ShopRequest.Status.PENDING,
    )


@pytest.mark.django_db
class TestShopRequestApprove:
    """admin_request_approve : crée Shop + envoie email/SMS + audit log."""

    def test_approve_creates_shop_and_audit_log(self, admin_client, shop_request):
        response = admin_client.post(f"/demandes/{shop_request.pk}/approuver/")
        assert response.status_code == 302
        # Une nouvelle Shop a été créée avec le slug désiré
        assert Shop.objects.filter(slug="future-boutique").exists()
        # Audit log existe avec action SHOP_APPROVED
        assert AdminAction.objects.filter(
            action=AdminAction.Action.SHOP_APPROVED,
        ).count() == 1

    def test_approve_request_becomes_approved(self, admin_client, shop_request):
        admin_client.post(f"/demandes/{shop_request.pk}/approuver/")
        shop_request.refresh_from_db()
        assert shop_request.status == ShopRequest.Status.APPROVED


@pytest.mark.django_db
class TestShopRequestReject:
    def test_reject_updates_status(self, admin_client, shop_request):
        response = admin_client.post(
            f"/demandes/{shop_request.pk}/rejeter/",
            {"admin_notes": "Slug déjà pris"},
        )
        assert response.status_code == 302
        shop_request.refresh_from_db()
        assert shop_request.status == ShopRequest.Status.REJECTED
        assert "déjà pris" in shop_request.admin_notes

    def test_reject_creates_audit_log(self, admin_client, shop_request):
        admin_client.post(
            f"/demandes/{shop_request.pk}/rejeter/",
            {"admin_notes": "Pas légitime"},
        )
        assert AdminAction.objects.filter(
            action=AdminAction.Action.SHOP_REJECTED,
        ).count() == 1


@pytest.mark.django_db
class TestShopToggleActive:
    def test_toggle_active_flips_flag(self, admin_client, shop):
        assert shop.is_active is True
        admin_client.post(f"/boutiques/{shop.pk}/toggle-active/")
        shop.refresh_from_db()
        assert shop.is_active is False
        # Re-toggle ↦ True
        admin_client.post(f"/boutiques/{shop.pk}/toggle-active/")
        shop.refresh_from_db()
        assert shop.is_active is True

    def test_toggle_creates_audit_log(self, admin_client, shop):
        admin_client.post(f"/boutiques/{shop.pk}/toggle-active/")
        assert AdminAction.objects.filter(
            action=AdminAction.Action.SHOP_TOGGLED,
        ).count() == 1


@pytest.mark.django_db
class TestShopUpdateCommission:
    def test_valid_rate_updates(self, admin_client, shop):
        response = admin_client.post(
            f"/boutiques/{shop.pk}/commission/",
            {"commission_rate": "10.5"},
        )
        assert response.status_code == 302
        shop.refresh_from_db()
        assert shop.commission_rate == Decimal("10.5")

    def test_rate_out_of_range_rejected(self, admin_client, shop):
        """Taux > 50% refusé."""
        admin_client.post(
            f"/boutiques/{shop.pk}/commission/",
            {"commission_rate": "75"},
        )
        shop.refresh_from_db()
        assert shop.commission_rate == Decimal("8.00")  # inchangé

    def test_invalid_rate_rejected(self, admin_client, shop):
        admin_client.post(
            f"/boutiques/{shop.pk}/commission/",
            {"commission_rate": "abc"},
        )
        shop.refresh_from_db()
        assert shop.commission_rate == Decimal("8.00")

    def test_audit_logs_old_and_new_rate(self, admin_client, shop):
        admin_client.post(
            f"/boutiques/{shop.pk}/commission/",
            {"commission_rate": "12"},
        )
        action = AdminAction.objects.get(
            action=AdminAction.Action.SHOP_COMMISSION_UPDATED,
        )
        assert action.meta["old_rate"] == "8.00"
        assert action.meta["new_rate"] == "12"


@pytest.mark.django_db
class TestCommissionMarkPaid:
    def test_marks_paid_with_reference_and_audit(self, admin_client, shop):
        order = Order.objects.create(
            shop=shop,
            client_name="C", client_phone="+221770000099",
            client_address="rue", client_city="Dakar",
            subtotal_xof=50000, total_xof=50000,
            commission_rate=Decimal("8.00"),
            commission_xof=4000, merchant_amount_xof=46000,
            payment_method=Order.PaymentMethod.CASH,
            status=Order.Status.PENDING,
        )
        commission = Commission.objects.create(
            order=order, shop=shop,
            sale_amount_xof=50000, rate=Decimal("8.00"),
            commission_xof=4000, merchant_amount_xof=46000,
            is_paid=False,
        )

        response = admin_client.post(
            f"/commissions/{commission.pk}/payer/",
            {"payout_reference": "WAVE-2026-001"},
        )
        assert response.status_code == 302

        commission.refresh_from_db()
        assert commission.is_paid is True
        assert commission.paid_at is not None
        assert commission.payout_reference == "WAVE-2026-001"

        # Audit log présent
        assert AdminAction.objects.filter(
            action=AdminAction.Action.COMMISSION_PAID,
        ).count() == 1


@pytest.mark.django_db
class TestSettingsUpdate:
    def test_updates_kill_switch_sms(self, admin_client):
        ps = PlatformSettings.load()
        assert ps.sms_enabled is True  # default

        admin_client.post("/reglages/update/", {
            "default_commission_rate": "8.00",
            "sms_enabled": "",  # unchecked = off
            "email_enabled": "on",
            "support_phone": "",
            "support_email": "",
            "maintenance_message": "",
        })

        ps = PlatformSettings.load()  # bypass cache via save() invalidation
        assert ps.sms_enabled is False

    def test_invalid_commission_rate_keeps_old_value(self, admin_client):
        ps = PlatformSettings.load()
        old_rate = ps.default_commission_rate

        admin_client.post("/reglages/update/", {
            "default_commission_rate": "200",  # out of range
            "sms_enabled": "on",
            "email_enabled": "on",
            "support_phone": "",
            "support_email": "",
            "maintenance_message": "",
        })

        ps = PlatformSettings.load()
        assert ps.default_commission_rate == old_rate

    def test_audit_log_created_on_update(self, admin_client):
        admin_client.post("/reglages/update/", {
            "default_commission_rate": "9.00",
            "sms_enabled": "on",
            "email_enabled": "on",
            "support_phone": "+221770099999",
            "support_email": "support@jappesi.sn",
            "maintenance_message": "",
        })
        assert AdminAction.objects.filter(
            action=AdminAction.Action.SETTINGS_UPDATED,
        ).count() == 1
