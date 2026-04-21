"""Signaux shops — invalidation du cache tenant."""
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import Shop


@receiver([post_save, post_delete], sender=Shop)
def invalidate_shop_cache(sender, instance, **kwargs):
    """Invalide le cache Redis du tenant quand le shop change."""
    cache.delete(f"shop:slug:{instance.slug}")
