"""
Codes promo d'une boutique.

Un coupon appartient à UN Shop. Un code est unique PAR boutique (pas
globalement) — deux commerçants peuvent avoir tous les deux un code
"SOLDES10".

Deux types de remise :
- PERCENTAGE : -10% (borné à 100)
- FIXED      : -500 XOF (montant fixe en XOF)

Règles d'application : min_order_xof (panier minimum), valid_from/until,
max_uses (nombre max de commandes l'utilisant).
"""
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Coupon(models.Model):
    class Type(models.TextChoices):
        PERCENTAGE = "percentage", "Pourcentage"
        FIXED = "fixed", "Montant fixe (XOF)"
        FREESHIP = "freeship", "Livraison offerte"

    shop = models.ForeignKey(
        "shops.Shop",
        on_delete=models.CASCADE,
        related_name="coupons",
    )
    code = models.CharField(
        max_length=40,
        help_text="Le client tape ce code au checkout. Majuscules conseillées.",
    )
    type = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.PERCENTAGE,
    )
    value = models.PositiveIntegerField(
        validators=[MinValueValidator(0)],
        default=0,
        help_text="Pour pourcentage : 10 pour -10%. Pour montant fixe : 500 pour -500 XOF. Pour livraison offerte : 0 (ignoré).",
    )
    one_per_customer = models.BooleanField(
        default=False,
        help_text="Chaque numéro de téléphone ne peut utiliser ce code qu'une fois.",
    )
    min_order_xof = models.PositiveIntegerField(
        default=0,
        help_text="Panier minimum requis (XOF). 0 = pas de minimum.",
    )
    max_uses = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Nombre max d'utilisations. Vide = illimité.",
    )
    uses_count = models.PositiveIntegerField(default=0)

    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(
        null=True, blank=True,
        help_text="Laisser vide pour un coupon sans date de fin.",
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Code promo"
        verbose_name_plural = "Codes promo"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["shop", "code"],
                name="unique_code_per_shop",
            ),
        ]
        indexes = [models.Index(fields=["shop", "is_active"])]

    def __str__(self):
        return f"{self.code} ({self.shop.slug})"

    def save(self, *args, **kwargs):
        self.code = self.code.upper().strip()
        super().save(*args, **kwargs)

    # ---- API métier ----

    def is_valid_now(self) -> bool:
        """Le coupon est-il applicable maintenant (actif, dans les dates, quota) ?"""
        if not self.is_active:
            return False
        now = timezone.now()
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        if self.max_uses is not None and self.uses_count >= self.max_uses:
            return False
        return True

    def compute_discount(self, subtotal_xof: int) -> int:
        """Retourne la remise SUR LE SOUS-TOTAL en XOF entier (hors livraison)."""
        if subtotal_xof < self.min_order_xof:
            return 0
        if self.type == self.Type.PERCENTAGE:
            discount = (subtotal_xof * self.value) // 100
        elif self.type == self.Type.FIXED:
            discount = self.value
        else:
            discount = 0  # freeship ne touche pas le subtotal
        return min(discount, subtotal_xof)

    def is_freeship(self) -> bool:
        return self.type == self.Type.FREESHIP

    def display_value(self) -> str:
        if self.type == self.Type.PERCENTAGE:
            return f"-{self.value}%"
        if self.type == self.Type.FREESHIP:
            return "Livraison offerte"
        return f"-{self.value} XOF"


class CouponUsage(models.Model):
    """Trace qui a utilisé quel coupon (pour la règle one_per_customer)."""
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name="usages")
    order = models.OneToOneField(
        "orders.Order", on_delete=models.CASCADE, related_name="coupon_usage",
    )
    client_phone = models.CharField(max_length=20, db_index=True)
    discount_xof = models.PositiveIntegerField(default=0)
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Utilisation de code promo"
        verbose_name_plural = "Utilisations de codes promo"
        ordering = ("-used_at",)
        indexes = [models.Index(fields=["coupon", "client_phone"])]
