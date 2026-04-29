"""Envoi du lien portail par SMS au livreur."""
import logging

from django.conf import settings

from ..models import Courier
from .tokens import make_courier_token

logger = logging.getLogger("jayma")


def send_portal_link(courier: Courier) -> None:
    """Envoie par SMS le lien portail au livreur."""
    token = make_courier_token(courier.pk)
    base = f"https://{courier.shop.slug}.{settings.JAYMA_ROOT_DOMAIN}"
    url = f"{base}/livreur/{token}/"

    text = (
        f"{courier.shop.name} te donne acces a tes courses sur Jappesi. "
        f"Ouvre : {url} (lien valable 90 jours)"
    )
    try:
        from notifications.services.sms import send_sms
        send_sms(courier.phone, text)
    except Exception:
        logger.exception("Échec envoi SMS portail pour courier %s", courier.pk)


def build_portal_url(courier: Courier, absolute: bool = True) -> str:
    """Retourne l'URL du portail pour copie/affichage."""
    token = make_courier_token(courier.pk)
    if absolute:
        base = f"https://{courier.shop.slug}.{settings.JAYMA_ROOT_DOMAIN}"
        return f"{base}/livreur/{token}/"
    return f"/livreur/{token}/"
