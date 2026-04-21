"""Tâches Celery pour le flow de demande de boutique."""
import logging
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

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

    subject = f"[Jayma] Nouvelle demande de boutique : {sr.shop_name}"
    body = f"""Bonjour,

Une nouvelle demande de boutique vient d'être reçue sur Jayma.

  Nom          : {sr.full_name}
  Email        : {sr.email}
  Téléphone    : {sr.phone}
  Ville        : {sr.city}
  Boutique     : {sr.shop_name}
  Slug demandé : {sr.desired_slug}.{settings.JAYMA_ROOT_DOMAIN}
  Catégorie    : {sr.product_category or "(non précisée)"}

Valider ou rejeter dans l'admin :
{admin_url}
"""
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[settings.DEFAULT_FROM_EMAIL],  # envoie à l'adresse Jayma par défaut
        fail_silently=False,
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

    password_block = ""
    if temp_password:
        password_block = (
            f"\n  Mot de passe temporaire : {temp_password}\n"
            f"  (change-le dès ta première connexion)\n"
        )

    # --- Email ---
    subject = f"Bienvenue sur Jayma — ta boutique {shop.name} est prête !"
    body = f"""Bonjour {owner.first_name or owner.username},

Bonne nouvelle : ta boutique {shop.name} est approuvée et en ligne !

  Ton adresse client   : {public_url}
  Ton dashboard        : {dashboard_url}
  Tes identifiants     : {owner.username}{password_block}

Tu peux maintenant ajouter tes produits, configurer ta boutique,
et partager ton lien sur WhatsApp.

À très vite,
L'équipe Jayma
"""
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[owner.email],
        fail_silently=True,
    )

    # --- SMS ---
    try:
        from notifications.services.sms import send_sms
        sms_text = (
            f"Felicitations ! Ta boutique Jayma est en ligne sur "
            f"{shop.slug}.{settings.JAYMA_ROOT_DOMAIN}. "
            f"Connecte-toi sur dashboard.{settings.JAYMA_ROOT_DOMAIN}"
        )
        send_sms(owner.phone, sms_text)
    except Exception:
        logger.exception("Échec SMS de bienvenue pour shop %s", shop_id)

    logger.info("Bienvenue envoyée pour shop %s.", shop_id)
