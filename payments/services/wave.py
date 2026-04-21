"""
Client Wave Sénégal — https://docs.wave.com/business

Flow :
1. Le commerçant a un Business ID Wave (WAVE_BUSINESS_ID).
2. On crée une "checkout session" pour un montant donné avec une URL de retour.
3. Wave retourne une "wave_launch_url" vers laquelle on redirige le client.
4. Le client paie via son app Wave → webhook POST sur nos endpoints.
5. La signature du webhook est un HMAC-SHA256 du corps avec WAVE_WEBHOOK_SECRET.
"""
import hmac
import hashlib
import logging
import requests
from django.conf import settings

logger = logging.getLogger("jayma")

WAVE_API_BASE = "https://api.wave.com/v1"
DEFAULT_TIMEOUT = 15  # secondes


class WaveError(Exception):
    """Erreur API Wave."""


def create_checkout_session(order, success_url: str, cancel_url: str) -> dict:
    """Crée une session de checkout Wave et retourne la réponse API."""
    if not settings.WAVE_API_KEY:
        raise WaveError("WAVE_API_KEY non configuré.")

    payload = {
        "amount": str(order.total_xof),
        "currency": "XOF",
        "error_url": cancel_url,
        "success_url": success_url,
        "client_reference": order.reference,
    }
    if settings.WAVE_BUSINESS_ID:
        payload["business_id"] = settings.WAVE_BUSINESS_ID

    headers = {
        "Authorization": f"Bearer {settings.WAVE_API_KEY}",
        "Content-Type": "application/json",
        "idempotency-key": f"jayma-{order.reference}",
    }
    try:
        response = requests.post(
            f"{WAVE_API_BASE}/checkout/sessions",
            json=payload,
            headers=headers,
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.exception("Wave API error pour order %s", order.reference)
        raise WaveError(f"Appel Wave échoué : {exc}") from exc
    return response.json()


def verify_webhook_signature(raw_body: bytes, signature_header: str) -> bool:
    """
    Vérifie la signature HMAC-SHA256 du webhook Wave.

    Wave envoie :
      Wave-Signature: t=<timestamp>,v1=<hexdigest>
    Le secret partagé est settings.WAVE_WEBHOOK_SECRET.
    """
    if not settings.WAVE_WEBHOOK_SECRET:
        logger.warning("WAVE_WEBHOOK_SECRET non configuré — signature non vérifiée.")
        return False
    if not signature_header:
        return False

    # Parse le header "t=...,v1=..."
    parts = dict(p.split("=", 1) for p in signature_header.split(",") if "=" in p)
    received_sig = parts.get("v1", "")
    timestamp = parts.get("t", "")

    signed_payload = f"{timestamp}.".encode() + raw_body
    expected = hmac.new(
        settings.WAVE_WEBHOOK_SECRET.encode(),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, received_sig)
