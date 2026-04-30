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
    """Backend AfricasTalking — prod et sandbox.

    En sandbox, AT n'autorise PAS les Sender ID custom (JAPPESI, etc.) — il
    faut laisser sender_id vide pour qu'AT utilise un numéro court par défaut.
    En production, on passe le Sender ID validé par AT (~1 semaine de review).
    """

    def __init__(self):
        import africastalking

        africastalking.initialize(settings.AT_USERNAME, settings.AT_API_KEY)
        self.sms = africastalking.SMS

    def send(self, to: str, message: str) -> dict:
        sender_id = getattr(settings, "AT_SENDER_ID", "") or ""
        kwargs = {}
        if sender_id.strip():
            kwargs["sender_id"] = sender_id.strip()
        return self.sms.send(message, [to], **kwargs)


def _get_backend() -> BaseSMSBackend:
    backend_path = getattr(
        settings,
        "SMS_BACKEND",
        "notifications.services.sms.ConsoleSMSBackend",
    )
    klass = import_string(backend_path)
    return klass()


def send_sms(to: str, message: str) -> NotificationLog:
    """Envoie un SMS et logue le résultat. Respecte le kill-switch PlatformSettings.sms_enabled.

    Le numéro est normalisé en E.164 (+221XXXXXXXXX) avant tout envoi : c'est
    indispensable pour AfricasTalking, qui ignore silencieusement les numéros
    sans préfixe pays.
    """
    from accounts.models import normalize_phone_sn
    from core.models import PlatformSettings

    # Garde-fou : normalisation E.164 obligatoire avant l'envoi
    try:
        to = normalize_phone_sn(to)
    except Exception as exc:
        log = NotificationLog.objects.create(
            channel=NotificationLog.Channel.SMS,
            recipient=str(to or ""),
            body=message,
            status=NotificationLog.Status.FAILED,
            error=f"Numéro invalide (non normalisable) : {exc}",
        )
        logger.warning("[SMS REJECTED] numéro invalide : %s", to)
        return log

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
        log.provider_response = response
        if _is_at_failure(response):
            log.status = NotificationLog.Status.FAILED
            log.error = _extract_at_error(response)
            logger.warning("AT a refusé le SMS vers %s : %s", to, log.error)
        else:
            log.status = NotificationLog.Status.SENT
            log.sent_at = timezone.now()
    except Exception as exc:
        log.status = NotificationLog.Status.FAILED
        log.error = str(exc)
        logger.exception("Échec envoi SMS vers %s", to)
    log.save()
    return log


def _is_at_failure(response) -> bool:
    """Détecte les réponses AT qui indiquent un échec malgré l'absence d'exception.

    AT renvoie un payload comme {SMSMessageData: {Message: 'InvalidSenderId',
    Recipients: []}} sans lever d'exception Python. Sans cette détection,
    le NotificationLog serait marqué 'sent' à tort.
    """
    if not isinstance(response, dict):
        return False
    msg_data = response.get("SMSMessageData")
    if not isinstance(msg_data, dict):
        return False
    recipients = msg_data.get("Recipients") or []
    if not recipients:
        # Recipients vide = aucun SMS envoyé
        return True
    # Recipients présent : on vérifie le statusCode de chacun
    for r in recipients:
        if not isinstance(r, dict):
            continue
        # Code 101 = Success ; 4xx / 5xx = échec
        if r.get("statusCode", 0) >= 200:
            return True
    return False


def _extract_at_error(response) -> str:
    """Extrait un message d'erreur lisible de la réponse AT."""
    if not isinstance(response, dict):
        return "Réponse AT inattendue."
    msg_data = response.get("SMSMessageData", {})
    top_msg = msg_data.get("Message", "")
    if top_msg and "Sent" not in top_msg:
        return f"AT a refusé : {top_msg}"
    recipients = msg_data.get("Recipients") or []
    if not recipients:
        return "AT a refusé : aucun destinataire accepté."
    statuses = ", ".join(str(r.get("status", "?")) for r in recipients)
    return f"AT a refusé : {statuses}"
