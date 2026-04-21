"""Tests de l'approbation de demande de boutique."""
import pytest
from django.contrib.auth import get_user_model

from shops.models import Shop, ShopRequest
from shops.services.approval import ApprovalError, approve_shop_request


User = get_user_model()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username="admin_test", email="admin@test.sn", password="pw",
        role=User.Role.ADMIN, phone="+221770000001",
    )


@pytest.fixture
def pending_request(db):
    return ShopRequest.objects.create(
        full_name="Fatou Test", email="fatou@test.sn",
        phone="+221778889977", city="Dakar",
        shop_name="Boutique Test", desired_slug="btest",
    )


class TestApproval:
    def test_creates_user_and_shop(self, pending_request, admin_user):
        shop, temp_pw = approve_shop_request(pending_request, reviewed_by=admin_user)

        assert shop.slug == "btest"
        assert shop.is_approved is True
        assert shop.owner.role == User.Role.MERCHANT
        assert shop.owner.email == "fatou@test.sn"
        assert temp_pw is not None
        assert len(temp_pw) > 8

        pending_request.refresh_from_db()
        assert pending_request.status == ShopRequest.Status.APPROVED
        assert pending_request.reviewed_by == admin_user

    def test_password_is_usable(self, pending_request, admin_user):
        shop, temp_pw = approve_shop_request(pending_request, reviewed_by=admin_user)
        # Le user doit pouvoir se logger avec le mot de passe
        assert shop.owner.check_password(temp_pw)

    def test_double_approval_raises(self, pending_request, admin_user):
        approve_shop_request(pending_request, reviewed_by=admin_user)
        with pytest.raises(ApprovalError):
            approve_shop_request(pending_request, reviewed_by=admin_user)

    def test_slug_collision_raises(self, pending_request, admin_user, shop):
        # La fixture `shop` a déjà pris le slug "testshop"
        pending_request.desired_slug = "testshop"
        pending_request.save()
        with pytest.raises(ApprovalError):
            approve_shop_request(pending_request, reviewed_by=admin_user)

    def test_existing_user_with_other_shop_raises(self, pending_request, admin_user, shop):
        # Forcer le même email que le merchant existant
        pending_request.email = shop.owner.email
        pending_request.save()
        with pytest.raises(ApprovalError):
            approve_shop_request(pending_request, reviewed_by=admin_user)
