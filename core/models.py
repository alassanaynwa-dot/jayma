"""Modèles transverses plateforme (singleton de réglages)."""
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class PlatformSettings(models.Model):
    """Réglages plateforme Jayma — singleton (pk=1 toujours)."""

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

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "PlatformSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
