"""
Backends SMS — AfricasTalking en prod, console en dev.

Utilisation :
    from notifications.services.sms import send_sms
    send_sms("+221771234567", "Votre commande est confirmée.")
"""
import logging

from django.conf import settings
from django.utils import timezone
from django.utils.module_loading import import_string

from notifications.models import NotificationLog

logger = logging.getLogger("jayma")


class BaseSMSBackend:
    def send(self, to: str, message: str) -> dict:
        raise NotImplementedError


class ConsoleSMSBackend(BaseSMSBackend):
    """En dev, on logge juste les SMS au lieu de les envoyer."""

    def send(self, to: str, message: str) -> dict:
        logger.info("[SMS DEV] %s → %s", to, message)
        return {"status": "logged"}


class AfricasTalkingSMSBackend(BaseSMSBackend):
    """Backend AfricasTalking — prod."""

    def __init__(self):
        import africastalking

        africastalking.initialize(settings.AT_USERNAME, settings.AT_API_KEY)
        self.sms = africastalking.SMS

    def send(self, to: str, message: str) -> dict:
        return self.sms.send(message, [to], sender_id=settings.AT_SENDER_ID)


def _get_backend() -> BaseSMSBackend:
    backend_path = getattr(
        settings,
        "SMS_BACKEND",
        "notifications.services.sms.ConsoleSMSBackend",
    )
    klass = import_string(backend_path)
    return klass()


def send_sms(to: str, message: str) -> NotificationLog:
    """Envoie un SMS et logue le résultat. Respecte le kill-switch PlatformSettings.sms_enabled."""
    from core.models import PlatformSettings

    log = NotificationLog.objects.create(
        channel=NotificationLog.Channel.SMS,
        recipient=to,
        body=message,
    )
    if not PlatformSettings.load().sms_enabled:
        log.status = NotificationLog.Status.FAILED
        log.error = "SMS désactivés globalement (Réglages plateforme)."
        log.save()
        logger.warning("[SMS BLOCKED] kill-switch actif → %s", to)
        return log
    try:
        response = _get_backend().send(to, message)
        log.status = NotificationLog.Status.SENT
        log.provider_response = response
        log.sent_at = timezone.now()
    except Exception as exc:
        log.status = NotificationLog.Status.FAILED
        log.error = str(exc)
        logger.exception("Échec envoi SMS vers %s", to)
    log.save()
    return log
