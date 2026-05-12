"""Tests du service SMS — pipeline complète : normalisation, kill-switch,
log NotificationLog, détection des refus AT silencieux.

L'app notifications est critique : SMS partent pour OTP, confirmation
commande, alerte stock, bienvenue boutique, etc. Avant ces tests, aucune
couverture automatisée.
"""
from unittest.mock import patch

import pytest

from core.models import PlatformSettings
from notifications.models import NotificationLog
from notifications.services.sms import (
    _extract_at_error,
    _is_at_failure,
    send_sms,
)


@pytest.mark.django_db
class TestSendSMSConsoleBackend:
    """En tests, on est sur ConsoleSMSBackend (dev). Vérifie qu'il logue OK."""

    def test_creates_log_with_sent_status(self):
        log = send_sms("+221770000123", "Hello test")
        assert log.pk is not None
        assert log.channel == NotificationLog.Channel.SMS
        assert log.recipient == "+221770000123"
        assert log.body == "Hello test"
        assert log.status == NotificationLog.Status.SENT
        assert log.error == ""

    def test_normalizes_phone_with_local_format(self):
        log = send_sms("770000456", "Hello")
        assert log.recipient == "+221770000456"
        assert log.status == NotificationLog.Status.SENT

    def test_normalizes_phone_with_separators(self):
        log = send_sms("77 000 04 57", "Hello")
        assert log.recipient == "+221770000457"
        assert log.status == NotificationLog.Status.SENT


@pytest.mark.django_db
class TestSendSMSPhoneValidation:
    def test_invalid_phone_returns_failed_log(self):
        log = send_sms("not-a-phone", "Hello")
        assert log.status == NotificationLog.Status.FAILED
        assert "invalide" in log.error.lower()

    def test_empty_phone_returns_failed_log(self):
        log = send_sms("", "Hello")
        assert log.status == NotificationLog.Status.FAILED

    def test_phone_too_short_returns_failed_log(self):
        log = send_sms("123", "Hello")
        assert log.status == NotificationLog.Status.FAILED


@pytest.mark.django_db
class TestSendSMSKillSwitch:
    """PlatformSettings.sms_enabled coupe tous les SMS d'un coup."""

    def test_kill_switch_off_blocks_send(self):
        ps = PlatformSettings.load()
        ps.sms_enabled = False
        ps.save()
        try:
            log = send_sms("+221770000999", "Should be blocked")
            assert log.status == NotificationLog.Status.FAILED
            assert "désactivés" in log.error.lower()
        finally:
            ps.sms_enabled = True
            ps.save()

    def test_kill_switch_on_allows_send(self):
        ps = PlatformSettings.load()
        ps.sms_enabled = True
        ps.save()
        log = send_sms("+221770000888", "Allowed")
        assert log.status == NotificationLog.Status.SENT


@pytest.mark.django_db
class TestSendSMSWithATBackend:
    """Tests avec backend AT mocké pour valider la détection des refus."""

    @patch("notifications.services.sms._get_backend")
    def test_at_refusal_with_invalid_sender_id_marks_failed(self, mock_get):
        """AT renvoie un payload qui contient InvalidSenderId → on detect."""
        backend = mock_get.return_value
        backend.send.return_value = {
            "SMSMessageData": {
                "Message": "InvalidSenderId",
                "Recipients": [],
            },
        }
        log = send_sms("+221770000222", "Test")
        assert log.status == NotificationLog.Status.FAILED
        assert "InvalidSenderId" in log.error

    @patch("notifications.services.sms._get_backend")
    def test_at_success_with_recipients_ok(self, mock_get):
        backend = mock_get.return_value
        backend.send.return_value = {
            "SMSMessageData": {
                "Message": "Sent to 1/1 Total Cost: USD 0.0200",
                "Recipients": [{
                    "statusCode": 101,
                    "status": "Success",
                    "number": "+221770000333",
                }],
            },
        }
        log = send_sms("+221770000333", "Test")
        assert log.status == NotificationLog.Status.SENT
        assert log.sent_at is not None

    @patch("notifications.services.sms._get_backend")
    def test_at_exception_marks_failed(self, mock_get):
        backend = mock_get.return_value
        backend.send.side_effect = ConnectionError("API timeout")
        log = send_sms("+221770000444", "Test")
        assert log.status == NotificationLog.Status.FAILED
        assert "timeout" in log.error.lower() or "API" in log.error


class TestATFailureDetectors:
    """Tests purs des helpers de détection AT (pas besoin de la BDD)."""

    def test_is_at_failure_with_empty_recipients(self):
        assert _is_at_failure({"SMSMessageData": {"Recipients": []}}) is True

    def test_is_at_failure_with_success_status(self):
        resp = {"SMSMessageData": {"Recipients": [{"statusCode": 101}]}}
        assert _is_at_failure(resp) is False

    def test_is_at_failure_with_error_status_code(self):
        resp = {"SMSMessageData": {"Recipients": [{"statusCode": 400}]}}
        assert _is_at_failure(resp) is True

    def test_is_at_failure_with_non_dict_response(self):
        assert _is_at_failure("garbage") is False
        assert _is_at_failure(None) is False

    def test_extract_at_error_with_top_level_message(self):
        resp = {"SMSMessageData": {"Message": "InvalidSenderId", "Recipients": []}}
        err = _extract_at_error(resp)
        assert "InvalidSenderId" in err

    def test_extract_at_error_with_recipients_status(self):
        resp = {"SMSMessageData": {
            "Message": "Sent",  # contient "Sent" → on regarde les recipients
            "Recipients": [{"status": "InvalidPhoneNumber"}],
        }}
        err = _extract_at_error(resp)
        assert "InvalidPhoneNumber" in err
