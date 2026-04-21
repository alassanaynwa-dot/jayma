"""
Tokens signés pour le portail livreur.

On ne crée PAS de compte User pour les livreurs (friction inutile au Sénégal).
Chaque livreur reçoit un lien signé par SMS qu'il ouvre depuis son téléphone
et qui lui donne accès à ses courses pendant 90 jours.
"""
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner

TOKEN_SALT = "delivery.courier_portal_v1"
TOKEN_MAX_AGE = 60 * 60 * 24 * 90  # 90 jours


def make_courier_token(courier_id: int) -> str:
    signer = TimestampSigner(salt=TOKEN_SALT)
    return signer.sign(str(courier_id))


def parse_courier_token(token: str) -> int | None:
    """Vérifie le token et retourne l'ID du livreur, ou None si invalide/expiré."""
    signer = TimestampSigner(salt=TOKEN_SALT)
    try:
        value = signer.unsign(token, max_age=TOKEN_MAX_AGE)
        return int(value)
    except (BadSignature, SignatureExpired, ValueError):
        return None
