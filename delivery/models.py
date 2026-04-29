"""
Modèles livraison — zones tarifées + Courier rattaché à une boutique.
"""
from django.core.validators import RegexValidator
from django.db import models

phone_validator = RegexValidator(
    regex=r"^(\+221)?[37][0-9]{8}$",
    message="Numéro sénégalais invalide.",
)


class DeliveryZone(models.Model):
    """
    Zone tarifée de livraison pour une boutique.

    Ex : "Dakar centre" (Plateau, Médina, Fann…) à 1 500 XOF,
         "Banlieue" (Pikine, Guédiawaye…) à 2 500 XOF,
         "Régions" (Thiès, Mbour…) à 5 000 XOF.
    """
    shop = models.ForeignKey(
        "shops.Shop",
        on_delete=models.CASCADE,
        related_name="delivery_zones",
    )
    name = models.CharField(max_length=80, help_text="Ex : Dakar centre")
    cities = models.TextField(
        help_text="Villes ou quartiers couverts, séparés par des virgules.",
    )
    fee_xof = models.PositiveIntegerField(help_text="Prix de livraison dans cette zone (XOF).")
    position = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Zone de livraison"
        verbose_name_plural = "Zones de livraison"
        ordering = ("position", "name")
        indexes = [models.Index(fields=["shop", "is_active"])]

    def __str__(self):
        return f"{self.name} ({self.fee_xof} XOF)"

    def city_list(self) -> list[str]:
        return [c.strip().lower() for c in (self.cities or "").split(",") if c.strip()]

    def covers(self, city_or_area: str) -> bool:
        needle = (city_or_area or "").strip().lower()
        if not needle:
            return False
        return any(needle == c or needle in c or c in needle for c in self.city_list())


class Courier(models.Model):
    """Livreur d'une boutique."""

    class Vehicle(models.TextChoices):
        MOTO = "moto", "Moto"
        SCOOTER = "scooter", "Scooter"
        CAR = "car", "Voiture"
        BIKE = "bike", "Vélo"
        FOOT = "foot", "À pied"

    shop = models.ForeignKey(
        "shops.Shop",
        on_delete=models.CASCADE,
        related_name="couriers",
    )
    name = models.CharField(max_length=100)
    phone = models.CharField(
        max_length=20,
        validators=[phone_validator],
        help_text="Format : +221 77 123 45 67",
    )
    vehicle = models.CharField(
        max_length=10,
        choices=Vehicle.choices,
        default=Vehicle.MOTO,
    )
    covered_zones = models.ManyToManyField(
        DeliveryZone,
        blank=True,
        related_name="couriers",
        help_text="Zones tarifées que ce livreur peut desservir.",
    )
    zones = models.CharField(
        max_length=200,
        blank=True,
        help_text="Quartiers couverts (notes libres, affichage uniquement).",
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Livreur"
        verbose_name_plural = "Livreurs"
        ordering = ("name",)
        indexes = [models.Index(fields=["shop", "is_active"])]

    def __str__(self):
        return f"{self.name} ({self.shop.slug})"

    def whatsapp_link(self) -> str:
        clean = self.phone.replace("+", "").replace(" ", "")
        return f"https://wa.me/{clean}"
