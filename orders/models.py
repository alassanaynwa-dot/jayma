"""
Modèles orders — commande + ligne de commande.

La commission est calculée au moment de la confirmation de paiement
et stockée en snapshot sur l'Order (on ne recalcule jamais à partir du
commission_rate du shop, qui pourrait changer entre-temps).
"""
import secrets

from django.db import models


def _generate_reference() -> str:
    """Référence commande unique, courte, lisible au téléphone."""
    return secrets.token_hex(4).upper()  # 8 caractères hex


class Order(models.Model):
    """Commande passée sur une boutique."""

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        CONFIRMED = "confirmed", "Confirmée"
        SHIPPED = "shipped", "Expédiée"
        DELIVERED = "delivered", "Livrée"
        CANCELLED = "cancelled", "Annulée"
        DISPUTED = "disputed", "Litige"

    class PaymentMethod(models.TextChoices):
        WAVE = "wave", "Wave"
        ORANGE_MONEY = "orange_money", "Orange Money"
        CINETPAY = "cinetpay", "CinetPay"
        CASH = "cash", "Paiement à la livraison"

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "En attente"
        PAID = "paid", "Payé"
        FAILED = "failed", "Échoué"
        REFUNDED = "refunded", "Remboursé"

    # Référence lisible (affichée au client, ex: JM-AB12CD34)
    reference = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        default=_generate_reference,
    )

    shop = models.ForeignKey(
        "shops.Shop",
        on_delete=models.PROTECT,
        related_name="orders",
    )

    # Info client (saisie au checkout, pas forcément un User enregistré)
    client_name = models.CharField(max_length=100)
    client_phone = models.CharField(max_length=20)
    client_email = models.EmailField(blank=True)
    client_address = models.TextField()
    client_city = models.CharField(max_length=100)
    client_notes = models.TextField(blank=True)

    # Montants en XOF entiers — SNAPSHOTS (ne changent pas si le rate shop change)
    subtotal_xof = models.PositiveIntegerField(default=0)
    delivery_xof = models.PositiveIntegerField(default=0)
    discount_xof = models.PositiveIntegerField(default=0)
    coupon_code = models.CharField(max_length=40, blank=True)
    total_xof = models.PositiveIntegerField(default=0)
    commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=0,
        help_text="Taux de commission appliqué à cette commande (snapshot).",
    )
    commission_xof = models.PositiveIntegerField(default=0)
    merchant_amount_xof = models.PositiveIntegerField(default=0)

    # État
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True,
    )
    tracking_number = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True, help_text="Notes internes commerçant.")

    # Livreur assigné (null tant que pas d'assignation)
    courier = models.ForeignKey(
        "delivery.Courier",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
    )

    # Notation livreur par le client (1 à 5 étoiles, optionnel)
    delivery_rating = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Note du client sur la livraison (1 à 5).",
    )
    delivery_rating_comment = models.TextField(
        blank=True,
        help_text="Commentaire optionnel du client sur la livraison.",
    )
    delivery_rated_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Commande"
        verbose_name_plural = "Commandes"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["shop", "status"]),
            models.Index(fields=["shop", "-created_at"]),
            # Composite pour les dashboards admin / commerçant qui filtrent
            # par payment_status et trient par date (revenus, commissions).
            # Devient critique à 10k+ commandes — anticipé maintenant pour
            # éviter une migration tardive sous charge.
            models.Index(fields=["payment_status", "-created_at"]),
        ]

    def __str__(self):
        return f"Commande {self.reference} — {self.total_xof} XOF"


class OrderItem(models.Model):
    """Ligne de commande — snapshot produit."""

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        "products.Product",
        null=True,
        on_delete=models.SET_NULL,
        help_text="Null si le produit a été supprimé après la commande.",
    )

    # Snapshots — jamais modifiés après la création
    product_name = models.CharField(max_length=200)
    unit_price_xof = models.PositiveIntegerField()
    quantity = models.PositiveIntegerField()

    @property
    def line_total_xof(self) -> int:
        return self.unit_price_xof * self.quantity

    class Meta:
        verbose_name = "Ligne de commande"
        verbose_name_plural = "Lignes de commande"

    def __str__(self):
        return f"{self.product_name} × {self.quantity}"
