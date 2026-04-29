"""
Service OTP pour auth client par téléphone.

Flow :
1. Client tape son numéro → send_otp() génère code 4 chiffres, envoie SMS, stocke DB
2. Client tape le code → verify_otp() vérifie et retourne le User (créé si nécessaire)

Sécurité :
- Code expire en 10 minutes
- Max 5 tentatives par code
- Max 3 envois par téléphone par 15 minutes (rate limit via Redis)
- Code invalidé après usage (consumed_at)
"""
from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

from ..models import OTPToken

logger = logging.getLogger("jayma")
User = get_user_model()


OTP_LIFETIME_MIN = 10
MAX_ATTEMPTS = 5
RATE_LIMIT_COUNT = 3
RATE_LIMIT_WINDOW_SEC = 15 * 60  # 15 minutes


@dataclass
class OTPResult:
    ok: bool
    user: object | None = None
    error: str | None = None


def _rate_key(phone: str) -> str:
    return f"otp:rate:{phone}"


def _normalize_phone(phone: str) -> str:
    return phone.replace(" ", "").strip()


# ============ Envoi ============

def send_otp(phone: str) -> OTPResult:
    """Génère et envoie un OTP au téléphone donné."""
    phone = _normalize_phone(phone)
    if not phone:
        return OTPResult(False, error="Numéro de téléphone requis.")

    # Rate limit : pas plus de 3 envois en 15 min
    key = _rate_key(phone)
    sent_count = cache.get(key, 0)
    if sent_count >= RATE_LIMIT_COUNT:
        return OTPResult(False, error="Trop de codes envoyés. Attends quelques minutes.")

    # Génère un code à 4 chiffres
    code = f"{secrets.randbelow(10000):04d}"
    expires_at = timezone.now() + timedelta(minutes=OTP_LIFETIME_MIN)

    OTPToken.objects.create(phone=phone, code=code, expires_at=expires_at)
    cache.set(key, sent_count + 1, timeout=RATE_LIMIT_WINDOW_SEC)

    # Envoi SMS (best-effort, n'échoue pas le flow)
    text = f"Ton code Jappesi : {code} (valable {OTP_LIFETIME_MIN} min). Ne le partage avec personne."
    try:
        from notifications.services.sms import send_sms
        send_sms(phone, text)
    except Exception:
        logger.exception("Échec envoi SMS OTP pour %s", phone)

    logger.info("OTP envoyé à %s (code masqué)", phone)
    return OTPResult(True)


# ============ Vérification ============

def verify_otp(phone: str, code: str, shop=None) -> OTPResult:
    """
    Vérifie un OTP et retourne le User client (créé si première connexion).
    Le user est global (pas scopé par boutique) — un même téléphone peut
    commander sur plusieurs boutiques avec le même compte.
    """
    phone = _normalize_phone(phone)
    code = (code or "").strip()
    if not (phone and code):
        return OTPResult(False, error="Numéro et code requis.")

    # Dernier OTP actif pour ce téléphone
    now = timezone.now()
    token = (
        OTPToken.objects
        .filter(phone=phone, consumed_at__isnull=True, expires_at__gte=now)
        .order_by("-created_at")
        .first()
    )
    if token is None:
        return OTPResult(False, error="Aucun code actif pour ce numéro. Demande un nouveau code.")

    if token.attempts >= MAX_ATTEMPTS:
        return OTPResult(False, error="Trop de tentatives. Demande un nouveau code.")

    if token.code != code:
        token.attempts += 1
        token.save(update_fields=["attempts"])
        return OTPResult(False, error="Code incorrect.")

    # OK → marquer consommé
    token.consumed_at = now
    token.save(update_fields=["consumed_at"])

    # Récupérer ou créer le User client
    user, created = User.objects.get_or_create(
        phone=phone,
        defaults={
            "username": f"client_{phone.lstrip('+')}",
            "role": User.Role.CLIENT,
            "phone_verified": True,
        },
    )
    if created:
        user.set_unusable_password()
        user.save()
        logger.info("Nouveau User client créé : %s", user.username)
    else:
        if not user.phone_verified:
            user.phone_verified = True
            user.save(update_fields=["phone_verified"])

    return OTPResult(True, user=user)
