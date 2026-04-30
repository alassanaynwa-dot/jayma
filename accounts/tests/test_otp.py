"""Tests de l'auth OTP client."""
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from accounts.models import OTPToken
from accounts.services.otp import MAX_ATTEMPTS, RATE_LIMIT_COUNT, send_otp, verify_otp


@pytest.fixture(autouse=True)
def _clear_cache():
    """Garantit l'isolation des tests qui utilisent le rate-limit Redis."""
    cache.clear()
    yield
    cache.clear()


class TestSendOTP:
    def test_generates_token(self, db):
        result = send_otp("+221770001122")
        assert result.ok is True
        token = OTPToken.objects.filter(phone="+221770001122").first()
        assert token is not None
        assert len(token.code) == 4
        assert token.code.isdigit()
        assert token.consumed_at is None

    def test_rate_limit(self, db):
        phone = "+221770009988"
        for _ in range(RATE_LIMIT_COUNT):
            assert send_otp(phone).ok is True
        # N+1 → refus
        result = send_otp(phone)
        assert result.ok is False
        assert "Trop" in result.error

    def test_empty_phone_refused(self, db):
        result = send_otp("")
        assert result.ok is False


class TestVerifyOTP:
    def test_valid_code_creates_user(self, db):
        send_otp("+221779998877")
        token = OTPToken.objects.filter(phone="+221779998877").last()
        result = verify_otp("+221779998877", token.code)
        assert result.ok is True
        assert result.user is not None
        assert result.user.phone == "+221779998877"
        assert result.user.role == "client"
        assert result.user.phone_verified is True

    def test_valid_code_reuses_existing_user(self, db):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        existing = User.objects.create_user(
            username="existing_client", phone="+221770000000",
            role=User.Role.CLIENT,
        )
        send_otp("+221770000000")
        token = OTPToken.objects.filter(phone="+221770000000").last()
        result = verify_otp("+221770000000", token.code)
        assert result.user.pk == existing.pk

    def test_wrong_code(self, db):
        send_otp("+221770001234")
        result = verify_otp("+221770001234", "9999")
        assert result.ok is False
        assert "incorrect" in result.error.lower()

    def test_consumed_code_refused(self, db):
        send_otp("+221770005544")
        token = OTPToken.objects.filter(phone="+221770005544").last()
        verify_otp("+221770005544", token.code)  # première utilisation OK
        result = verify_otp("+221770005544", token.code)
        assert result.ok is False

    def test_expired_code_refused(self, db):
        OTPToken.objects.create(
            phone="+221770007777", code="1234",
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        result = verify_otp("+221770007777", "1234")
        assert result.ok is False

    def test_max_attempts(self, db):
        send_otp("+221770003333")
        for _ in range(MAX_ATTEMPTS):
            verify_otp("+221770003333", "0000")
        # Même le bon code est refusé après N tentatives
        token = OTPToken.objects.filter(phone="+221770003333").last()
        result = verify_otp("+221770003333", token.code)
        assert result.ok is False
