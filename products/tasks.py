"""Tâches Celery pour products — notifications retour en stock."""
import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import Product, StockAlert

logger = logging.getLogger("jayma")


@shared_task
def notify_stock_back(product_id: int) -> int:
    """
    Envoie un SMS à chaque client qui avait demandé une alerte sur ce produit.
    Retourne le nombre de notifications envoyées.
    """
    try:
        product = Product.objects.select_related("shop").get(pk=product_id)
    except Product.DoesNotExist:
        return 0

    if product.stock <= 0:
        return 0

    shop = product.shop
    root = settings.JAYMA_ROOT_DOMAIN
    url = f"{shop.slug}.{root}/produits/{product.slug}/"

    pending = StockAlert.objects.filter(product=product, notified_at__isnull=True)
    count = 0
    for alert in pending:
        text = (
            f"Bonne nouvelle ! « {product.name[:40]} » est de nouveau en stock "
            f"chez {shop.name}. Commande vite : {url}"
        )
        try:
            from notifications.services.sms import send_sms
            send_sms(alert.client_phone, text)
            alert.notified_at = timezone.now()
            alert.save(update_fields=["notified_at"])
            count += 1
        except Exception:
            logger.exception("Échec SMS alerte stock pour %s", alert.client_phone)

    logger.info("Alertes stock : %d SMS envoyés pour %s", count, product.name)
    return count
