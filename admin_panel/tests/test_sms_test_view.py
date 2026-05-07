"""Tests de la page admin /notifications/test-sms/.

Cette page sert d'outil de debug en prod : on entre un numéro + un message,
on envoie via la pipeline complète (normalisation + kill-switch + log), et
on voit la réponse provider brute. Les tests vérifient que :
- Seuls les admins plateforme y accèdent
- Le formulaire s'affiche correctement
- Un POST valide crée bien un NotificationLog (en sandbox via ConsoleSMSBackend)
- Les erreurs de saisie (champs vides) sont signalées
- Le kill-switch SMS est respecté
"""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from core.models import PlatformSettings
from notifications.models import NotificationLog

User = get_user_model()

ADMIN_HOST = "admin.jayma.local"
URL_SMS_TEST = "/notifications/test-sms/"


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username="admin1", phone="+221770000001", email="admin@x.sn",
        password="adminpass123", role=User.Role.ADMIN,
    )


@pytest.fixture
def merchant_user(db):
    return User.objects.create_user(
        username="merch1", phone="+221770000002", email="merch@x.sn",
        password="merchpass123", role=User.Role.MERCHANT,
    )


@pytest.fixture
def admin_client(admin_user):
    c = Client(HTTP_HOST=ADMIN_HOST)
    c.force_login(admin_user)
    return c


@pytest.mark.django_db
class TestAccessControl:
    def test_anonymous_redirected_to_login(self):
        c = Client(HTTP_HOST=ADMIN_HOST)
        response = c.get(URL_SMS_TEST)
        # login_required → redirige vers /comptes/login/
        assert response.status_code in (301, 302)
        assert "/login" in response["Location"]

    def test_merchant_forbidden(self, merchant_user):
        c = Client(HTTP_HOST=ADMIN_HOST)
        c.force_login(merchant_user)
        response = c.get(URL_SMS_TEST)
        assert response.status_code == 403

    def test_admin_can_access(self, admin_client):
        response = admin_client.get(URL_SMS_TEST)
        assert response.status_code == 200


@pytest.mark.django_db
class TestFormDisplay:
    def test_get_shows_form_and_config(self, admin_client):
        response = admin_client.get(URL_SMS_TEST)
        body = response.content
        # Présence du formulaire
        assert b'name="phone"' in body
        assert b'name="message"' in body
        # Block config affiché (Backend, AT Username, Sender ID)
        assert b"Configuration actuelle" in body
        assert b"Backend" in body
        # En tests on est sur ConsoleSMSBackend (settings dev)
        assert b"ConsoleSMSBackend" in body or b"DEV" in body

    def test_default_message_prefilled(self, admin_client):
        response = admin_client.get(URL_SMS_TEST)
        # Le message par défaut doit être pré-rempli
        assert b"Test SMS Jappesi" in response.content


@pytest.mark.django_db
class TestSendSMS:
    def test_post_valid_creates_notification_log(self, admin_client):
        before = NotificationLog.objects.count()
        response = admin_client.post(URL_SMS_TEST, {
            "phone": "+221770001234",
            "message": "Hello from test",
        })
        assert response.status_code == 200
        # Un nouveau log a été créé
        assert NotificationLog.objects.count() == before + 1
        log = NotificationLog.objects.latest("created_at")
        assert log.channel == NotificationLog.Channel.SMS
        assert log.recipient == "+221770001234"
        assert log.body == "Hello from test"
        # En console backend, status = sent
        assert log.status == NotificationLog.Status.SENT
        # Le log apparaît dans le rendu
        assert b"R\xc3\xa9sultat" in response.content  # "Résultat"

    def test_post_normalizes_phone_without_prefix(self, admin_client):
        admin_client.post(URL_SMS_TEST, {
            "phone": "770001234",  # sans +221
            "message": "Test normalisation",
        })
        log = NotificationLog.objects.latest("created_at")
        assert log.recipient == "+221770001234"

    def test_post_empty_phone_shows_error(self, admin_client):
        before = NotificationLog.objects.count()
        response = admin_client.post(URL_SMS_TEST, {
            "phone": "",
            "message": "Hello",
        })
        assert response.status_code == 200
        # Aucun log créé
        assert NotificationLog.objects.count() == before
        # Le message d'erreur Django est dans la réponse
        assert b"requis" in response.content

    def test_post_empty_message_shows_error(self, admin_client):
        before = NotificationLog.objects.count()
        response = admin_client.post(URL_SMS_TEST, {
            "phone": "+221770001234",
            "message": "",
        })
        assert response.status_code == 200
        assert NotificationLog.objects.count() == before

    def test_post_invalid_phone_creates_failed_log(self, admin_client):
        """Numéro non normalisable → log créé avec status=failed."""
        admin_client.post(URL_SMS_TEST, {
            "phone": "abc-not-a-phone",
            "message": "Hello",
        })
        log = NotificationLog.objects.latest("created_at")
        assert log.status == NotificationLog.Status.FAILED
        assert "invalide" in log.error.lower()

    def test_kill_switch_blocks_send(self, admin_client):
        """Quand PlatformSettings.sms_enabled=False, le SMS est bloqué."""
        ps = PlatformSettings.load()
        ps.sms_enabled = False
        ps.save()
        try:
            admin_client.post(URL_SMS_TEST, {
                "phone": "+221770001234",
                "message": "Should be blocked",
            })
            log = NotificationLog.objects.latest("created_at")
            assert log.status == NotificationLog.Status.FAILED
            assert "désactivés" in log.error.lower()
        finally:
            ps.sms_enabled = True
            ps.save()
