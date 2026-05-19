"""Tâches Celery pour la relance des paniers abandonnés."""
import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from notifications.services.sms import send_sms

from .models import AbandonedCart

logger = logging.getLogger("jayma")


# Fenêtre de relance : paniers abandonnés entre 2h et 7 jours
REMIND_MIN_AGE_HOURS = 2
REMIND_MAX_AGE_DAYS = 7


@shared_task
def send_cart_reminders() -> int:
    """
    Tâche planifiée : trouve les paniers abandonnés éligibles et envoie un SMS.

    Éligibilité :
    - last_seen_at entre 2h et 7 jours dans le passé
    - reminded_at IS NULL (pas déjà relancé)
    - recovered_at IS NULL (la commande n'a pas été finalisée)

    À programmer via django_celery_beat (voir management command setup_cart_reminders).
    """
    now = timezone.now()
    min_age = now - timedelta(hours=REMIND_MIN_AGE_HOURS)
    max_age = now - timedelta(days=REMIND_MAX_AGE_DAYS)

    eligible = AbandonedCart.objects.select_related("shop").filter(
        last_seen_at__lte=min_age,
        last_seen_at__gte=max_age,
        reminded_at__isnull=True,
        recovered_at__isnull=True,
    )

    count = 0
    for ac in eligible:
        _send_reminder_sms(ac)
        count += 1

    logger.info("send_cart_reminders : %d rappels envoyés", count)
    return count


def _send_reminder_sms(ac: AbandonedCart) -> None:
    root = settings.JAYMA_ROOT_DOMAIN
    first_name = (ac.client_name or "").split(" ")[0] or "là"
    items_count = sum(i.get("quantity", 1) for i in ac.items_json)
    article = "article" if items_count == 1 else "articles"
    text = (
        f"Salut {first_name} ! Tu as laissé {items_count} {article} dans ton panier "
        f"chez {ac.shop.name}. Finalise ta commande : "
        f"{ac.shop.slug}.{root}/panier/"
    )
    try:
        send_sms(ac.client_phone, text)
        ac.reminded_at = timezone.now()
        ac.save(update_fields=["reminded_at"])
    except Exception:
        logger.exception("Échec SMS relance pour %s", ac.client_phone)
