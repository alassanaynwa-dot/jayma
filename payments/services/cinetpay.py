"""
Client CinetPay — https://docs.cinetpay.com/api/1.0-fr/

Agrégateur qui couvre Wave, Orange Money, Free Money, cartes bancaires.
Flow :
1. POST /payment avec transaction_id unique → retourne payment_url + payment_token.
2. Redirect client vers payment_url.
3. Client paie → CinetPay POST webhook sur notify_url.
4. On RE-VÉRIFIE via /payment/check pour confirmer (best practice CinetPay).
"""
import hashlib
import hmac
import logging

import requests
from django.conf import settings

logger = logging.getLogger("jayma")

CINETPAY_API_BASE = "https://api-checkout.cinetpay.com/v2"
DEFAULT_TIMEOUT = 15


class CinetPayError(Exception):
    pass


def create_payment(order, return_url: str, notify_url: str) -> dict:
    if not settings.CINETPAY_API_KEY:
        raise CinetPayError("CINETPAY_API_KEY non configuré.")

    payload = {
        "apikey": settings.CINETPAY_API_KEY,
        "site_id": settings.CINETPAY_SITE_ID,
        "transaction_id": order.reference,
        "amount": order.total_xof,
        "currency": "XOF",
        "description": f"Commande {order.reference} — {order.shop.name}"[:120],
        "return_url": return_url,
        "notify_url": notify_url,
        "customer_name": order.client_name[:50],
        "customer_surname": " ",
        "customer_phone_number": order.client_phone,
        "customer_email": order.client_email or "noreply@jappesi.sn",
        "customer_address": order.client_address[:200],
        "customer_city": order.client_city[:50],
        "customer_country": "SN",
        "customer_state": "SN",
        "customer_zip_code": "11000",
        "channels": "ALL",
        "lang": "FR",
    }
    try:
        response = requests.post(
            f"{CINETPAY_API_BASE}/payment",
            json=payload,
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.exception("CinetPay API error pour order %s", order.reference)
        raise CinetPayError(f"Appel CinetPay échoué : {exc}") from exc
    data = response.json()
    if data.get("code") != "201":
        raise CinetPayError(f"CinetPay refuse : {data.get('message')}")
    return data


def check_payment_status(transaction_id: str) -> dict:
    """Ré-interroge CinetPay pour confirmer le statut — toujours appeler après webhook."""
    payload = {
        "apikey": settings.CINETPAY_API_KEY,
        "site_id": settings.CINETPAY_SITE_ID,
        "transaction_id": transaction_id,
    }
    try:
        response = requests.post(
            f"{CINETPAY_API_BASE}/payment/check",
            json=payload,
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise CinetPayError(f"Check CinetPay échoué : {exc}") from exc
    return response.json()


def verify_hmac(raw_body: bytes, received_token: str) -> bool:
    """CinetPay envoie un token HMAC dans le header — à vérifier."""
    if not settings.CINETPAY_SECRET_KEY:
        return False
    expected = hmac.new(
        settings.CINETPAY_SECRET_KEY.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, received_token or "")
