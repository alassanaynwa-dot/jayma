"""Signaux products — alertes retour en stock."""
import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Product

logger = logging.getLogger("jayma")


@receiver(pre_save, sender=Product)
def _remember_old_stock(sender, instance, **kwargs):
    """Mémorise le stock AVANT save pour détecter les transitions."""
    if instance.pk:
        try:
            old = Product.objects.only("stock").get(pk=instance.pk)
            instance._old_stock = old.stock
        except Product.DoesNotExist:
            instance._old_stock = None
    else:
        instance._old_stock = None


@receiver(post_save, sender=Product)
def _trigger_stock_alerts(sender, instance, created, **kwargs):
    """
    Si le stock vient de passer de 0 à >0, on notifie tous les
    clients qui avaient demandé une alerte.
    """
    if created:
        return
    old = getattr(instance, "_old_stock", None)
    if old is None or old > 0 or instance.stock <= 0:
        return

    # Stock vient de revenir — async via Celery task
    try:
        from .tasks import notify_stock_back
        notify_stock_back.delay(instance.pk)
    except Exception:
        logger.exception("Échec dispatch notify_stock_back pour product %s", instance.pk)
