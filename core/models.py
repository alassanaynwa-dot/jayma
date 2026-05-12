"""Modèles transverses plateforme (singleton de réglages)."""
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class PlatformSettings(models.Model):
    """Réglages plateforme Jappesi — singleton (pk=1 toujours)."""

    default_commission_rate = models.DecimalField(
        "Taux de commission par défaut (%)",
        max_digits=5,
        decimal_places=2,
        default=Decimal("8.00"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("50"))],
        help_text="Appliqué automatiquement aux nouvelles boutiques.",
    )
    sms_enabled = models.BooleanField(
        "SMS activés",
        default=True,
        help_text="Coupe-circuit global pour les envois SMS.",
    )
    email_enabled = models.BooleanField(
        "Emails activés",
        default=True,
        help_text="Coupe-circuit global pour les envois email.",
    )
    support_phone = models.CharField(
        "Téléphone support",
        max_length=20,
        blank=True,
    )
    support_email = models.EmailField(
        "Email support",
        blank=True,
    )
    maintenance_message = models.TextField(
        "Message maintenance",
        blank=True,
        help_text="Si renseigné, affiché en bannière dans toutes les boutiques.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Réglages plateforme"
        verbose_name_plural = "Réglages plateforme"

    def __str__(self):
        return "Réglages plateforme"

    CACHE_KEY = "platform_settings:singleton"
    CACHE_TIMEOUT = 600  # 10 min — invalidation explicite via save()

    def save(self, *args, **kwargs):
        from django.core.cache import cache
        self.pk = 1
        super().save(*args, **kwargs)
        # Invalider le cache : le prochain load() relira depuis la BDD
        cache.delete(self.CACHE_KEY)

    @classmethod
    def load(cls) -> "PlatformSettings":
        """Charge le singleton — caché Redis 10 min pour éviter les hits SQL.

        Cette méthode est appelée à chaque envoi SMS (kill-switch) et à
        chaque request dashboard (théoriquement) → ~100s appels/jour. Sans
        cache, c'est ~100s SELECT * FROM core_platformsettings/jour. Avec
        cache, c'est 1 SELECT toutes les 10 min, sauf invalidation.
        """
        from django.core.cache import cache
        cached = cache.get(cls.CACHE_KEY)
        if cached is not None:
            return cached
        obj, _ = cls.objects.get_or_create(pk=1)
        cache.set(cls.CACHE_KEY, obj, cls.CACHE_TIMEOUT)
        return obj
