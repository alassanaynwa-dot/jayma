"""
Modèles commissions — suivi de ce que Jayma doit reverser au commerçant.
"""
from django.db import models


class Commission(models.Model):
    """Commission Jayma + montant à reverser au commerçant pour UNE commande."""

    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="commission",
    )
    shop = models.ForeignKey(
        "shops.Shop",
        on_delete=models.PROTECT,
        related_name="commissions",
    )
    sale_amount_xof = models.PositiveIntegerField()
    rate = models.DecimalField(max_digits=5, decimal_places=2)
    commission_xof = models.PositiveIntegerField()
    merchant_amount_xof = models.PositiveIntegerField()

    is_paid = models.BooleanField(
        default=False,
        help_text="Reversement effectué au commerçant ?",
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    payout_reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="Référence du virement/transfert au commerçant.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Commission"
        verbose_name_plural = "Commissions"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["shop", "is_paid"]),
        ]

    def __str__(self):
        return f"Commission commande {self.order.reference} : {self.commission_xof} XOF"
