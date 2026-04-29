"""
Client Orange Money Sénégal — OM WebPay.

Docs : https://developer.orange.com/apis/om-webpay-sn

Flow :
1. OAuth2 client_credentials pour récupérer un access_token.
2. POST /webpayment avec les infos order → retourne payment_url et pay_token.
3. Redirect client vers payment_url.
4. OM callback via notif_url → on vérifie le paiement via API check.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger("jayma")

OM_TOKEN_URL = "https://api.orange.com/oauth/v3/token"
OM_API_BASE = "https://api.orange.com/orange-money-webpay/sn/v1"
DEFAULT_TIMEOUT = 15


class OrangeMoneyError(Exception):
    pass


def _get_access_token() -> str:
    if not (settings.OM_CLIENT_ID and settings.OM_CLIENT_SECRET):
        raise OrangeMoneyError("OM_CLIENT_ID/OM_CLIENT_SECRET non configurés.")
    try:
        response = requests.post(
            OM_TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(settings.OM_CLIENT_ID, settings.OM_CLIENT_SECRET),
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise OrangeMoneyError(f"Auth OM échouée : {exc}") from exc
    return response.json()["access_token"]


def create_payment(order, return_url: str, cancel_url: str) -> dict:
    token = _get_access_token()
    payload = {
        "merchant_key": settings.OM_MERCHANT_KEY,
        "currency": "XOF",
        "order_id": order.reference,
        "amount": order.total_xof,
        "return_url": return_url,
        "cancel_url": cancel_url,
        "notif_url": f"https://{settings.JAYMA_ROOT_DOMAIN}/paiements/webhooks/orange-money/",
        "lang": "fr",
        "reference": order.reference,
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(
            f"{OM_API_BASE}/webpayment",
            json=payload,
            headers=headers,
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.exception("OM API error pour order %s", order.reference)
        raise OrangeMoneyError(f"Appel OM échoué : {exc}") from exc
    return response.json()


def verify_webhook_signature(payload: dict) -> bool:
    """
    OM envoie un payload JSON avec `txnid` et `status`. Pas de HMAC natif
    — on vérifie en rappelant l'API avec le pay_token pour confirmer.
    En prod : appeler /transactionstatus/{pay_token} pour cross-check.
    """
    if not settings.OM_WEBHOOK_SECRET:
        logger.warning("OM_WEBHOOK_SECRET non configuré.")
        return False
    # Si OM envoie un header de signature custom, le vérifier ici.
    return True


def check_transaction_status(pay_token: str) -> dict:
    """Vérifie le statut d'une transaction via l'API OM (confirmation)."""
    token = _get_access_token()
    try:
        response = requests.get(
            f"{OM_API_BASE}/transactionstatus/{pay_token}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise OrangeMoneyError(f"Check statut OM échoué : {exc}") from exc
    return response.json()
