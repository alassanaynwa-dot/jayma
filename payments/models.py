"""
Modèles payments — transaction + webhooks.

Un Payment représente UNE tentative de paiement. Une Order peut avoir
plusieurs Payment (ex: première tentative échouée, deuxième réussie).
"""
from django.db import models


class Payment(models.Model):
    """Tentative de paiement sur une Order via un provider."""

    class Provider(models.TextChoices):
        WAVE = "wave", "Wave"
        ORANGE_MONEY = "orange_money", "Orange Money"
        CINETPAY = "cinetpay", "CinetPay"
        CASH = "cash", "Cash à la livraison"

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        SUCCESS = "success", "Succès"
        FAILED = "failed", "Échec"
        CANCELLED = "cancelled", "Annulé"

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="payments",
    )
    provider = models.CharField(max_length=20, choices=Provider.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    amount_xof = models.PositiveIntegerField()

    # Référence côté provider (transaction_id Wave, txn CinetPay, etc.)
    provider_reference = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
    )
    provider_payload = models.JSONField(
        default=dict, blank=True,
        help_text="Réponse brute du provider (pour debug).",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["provider", "provider_reference"]),
        ]

    def __str__(self):
        return f"{self.get_provider_display()} — {self.amount_xof} XOF ({self.get_status_display()})"


class WebhookEvent(models.Model):
    """
    Log de tous les webhooks reçus des providers.

    On stocke le payload brut pour pouvoir rejouer / débugger, et on
    marque processed=True une fois traité pour idempotence.
    """
    provider = models.CharField(max_length=20)
    event_id = models.CharField(max_length=200, db_index=True)
    payload = models.JSONField(default=dict)
    signature_valid = models.BooleanField(default=False)
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Événement webhook"
        verbose_name_plural = "Événements webhooks"
        unique_together = [("provider", "event_id")]
        ordering = ("-received_at",)

    def __str__(self):
        return f"{self.provider}/{self.event_id}"
