"""Tâches Celery pour le flow de demande de boutique."""
import logging

from celery import shared_task
from django.conf import settings

from core.services.emails import send_branded_email
from shops.models import Shop, ShopRequest

logger = logging.getLogger("jayma")


@shared_task
def notify_admin_of_new_request(request_id: int) -> None:
    """Envoie un email à l'admin quand une nouvelle demande arrive."""
    try:
        sr = ShopRequest.objects.get(pk=request_id)
    except ShopRequest.DoesNotExist:
        logger.warning("ShopRequest %s introuvable pour notification.", request_id)
        return

    admin_url = f"https://admin.{settings.JAYMA_ROOT_DOMAIN}/shops/shoprequest/{sr.pk}/change/"

    send_branded_email(
        subject=f"[Jappesi] Nouvelle demande de boutique : {sr.shop_name}",
        recipients=[settings.DEFAULT_FROM_EMAIL],
        template_name="admin_new_shop_request",
        context={"sr": sr, "admin_url": admin_url, "recipient_label": "l'équipe Jappesi"},
    )
    logger.info("Notification admin envoyée pour demande %s.", request_id)


@shared_task
def send_merchant_welcome(shop_id: int, temp_password: str | None = None) -> None:
    """Envoie email + SMS de bienvenue au commerçant après approbation."""
    try:
        shop = Shop.objects.select_related("owner").get(pk=shop_id)
    except Shop.DoesNotExist:
        logger.warning("Shop %s introuvable pour bienvenue.", shop_id)
        return

    owner = shop.owner
    public_url = shop.get_public_url()
    dashboard_url = f"https://dashboard.{settings.JAYMA_ROOT_DOMAIN}/"

    send_branded_email(
        subject=f"Bienvenue sur Jappesi — ta boutique {shop.name} est prête !",
        recipients=[owner.email],
        template_name="merchant_welcome",
        context={
            "shop": shop,
            "owner": owner,
            "public_url": public_url,
            "dashboard_url": dashboard_url,
            "temp_password": temp_password,
            "recipient_label": owner.email,
        },
        fail_silently=True,
    )

    # --- SMS (inchangé, on garde le format court existant) ---
    try:
        from notifications.services.sms import send_sms
        sms_text = (
            f"Felicitations ! Ta boutique Jappesi est en ligne sur "
            f"{shop.slug}.{settings.JAYMA_ROOT_DOMAIN}. "
            f"Connecte-toi sur dashboard.{settings.JAYMA_ROOT_DOMAIN}"
        )
        send_sms(owner.phone, sms_text)
    except Exception:
        logger.exception("Échec SMS de bienvenue pour shop %s", shop_id)

    logger.info("Bienvenue envoyée pour shop %s.", shop_id)
