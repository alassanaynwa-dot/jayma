"""
Modèles cart — panier abandonné en DB pour la relance SMS.

Le panier actif reste en session (volatile). Dès qu'on connaît le phone
du client (user connecté OU champ phone rempli au checkout), on fait un
snapshot en DB pour pouvoir relancer si la commande n'est pas finalisée.
"""
from django.db import models


class AbandonedCart(models.Model):
    """Snapshot d'un panier abandonné — 1 seul par (shop, phone)."""
    shop = models.ForeignKey(
        "shops.Shop",
        on_delete=models.CASCADE,
        related_name="abandoned_carts",
    )
    client_phone = models.CharField(max_length=20, db_index=True)
    client_name = models.CharField(max_length=100, blank=True)

    items_json = models.JSONField(
        default=list,
        help_text="Snapshot des items : [{product_id, name, unit_price, quantity}, ...]",
    )
    total_xof = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    reminded_at = models.DateTimeField(null=True, blank=True)
    recovered_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Rempli quand une Order est créée — évite les relances inutiles.",
    )

    class Meta:
        verbose_name = "Panier abandonné"
        verbose_name_plural = "Paniers abandonnés"
        unique_together = [("shop", "client_phone")]
        ordering = ("-last_seen_at",)
        indexes = [
            models.Index(fields=["shop", "reminded_at", "recovered_at"]),
        ]

    def __str__(self):
        return f"{self.client_phone} → {self.shop.slug} ({self.total_xof} XOF)"
