"""
Modèles shops — boutique + demande de création.

Un Shop appartient à un User (OneToOne). Avant d'être créé en dur,
il passe par une ShopRequest validée par un admin.
"""
from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

# Slug de boutique : lettres minuscules, chiffres, tirets, 3-40 caractères
slug_validator = RegexValidator(
    regex=r"^[a-z0-9]([a-z0-9-]{1,38}[a-z0-9])$",
    message="Le slug doit contenir uniquement des lettres, chiffres et tirets (3 à 40 caractères).",
)


class ShopRequest(models.Model):
    """Demande de création d'une boutique, en attente de validation."""

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        APPROVED = "approved", "Approuvée"
        REJECTED = "rejected", "Rejetée"

    # Infos demandeur (le User peut ne pas encore exister)
    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    city = models.CharField(max_length=100)

    # Infos boutique souhaitées
    shop_name = models.CharField(max_length=100)
    desired_slug = models.SlugField(
        max_length=40,
        validators=[slug_validator],
        help_text="3-40 caractères, lettres minuscules, chiffres, tirets.",
    )
    description = models.TextField(blank=True)
    product_category = models.CharField(
        max_length=100,
        blank=True,
        help_text="Ex : vêtements, cosmétiques, électronique...",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    admin_notes = models.TextField(blank=True, help_text="Notes internes admin.")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="shop_requests_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Demande de boutique"
        verbose_name_plural = "Demandes de boutiques"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.shop_name} ({self.get_status_display()})"


class Shop(models.Model):
    """Boutique d'un commerçant — accessible sur <slug>.jappesi.sn."""

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="shop",
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(
        max_length=40,
        unique=True,
        validators=[slug_validator],
        db_index=True,
    )
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to="shops/logos/", blank=True, null=True)
    banner = models.ImageField(upload_to="shops/banners/", blank=True, null=True)

    # Contact affiché sur la boutique publique
    phone = models.CharField(max_length=20)
    whatsapp = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    city = models.CharField(max_length=100)
    address = models.TextField(blank=True)

    # État
    is_approved = models.BooleanField(
        default=False,
        help_text="Validé par l'admin Jappesi.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Le commerçant peut désactiver temporairement sa boutique.",
    )

    # Commission — modifiable par l'admin boutique par boutique
    commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=8.00,
        help_text="Pourcentage prélevé par Jappesi sur chaque vente (ex: 8.00 = 8%).",
    )

    # Theme (extensible plus tard)
    theme_color = models.CharField(
        max_length=7,
        default="#D97706",
        help_text="Couleur principale de la boutique (hex).",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Boutique"
        verbose_name_plural = "Boutiques"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.name} ({self.slug})"

    def get_public_url(self) -> str:
        """URL publique complète de la boutique."""
        from django.conf import settings as dj_settings
        return f"https://{self.slug}.{dj_settings.JAYMA_ROOT_DOMAIN}"


class WaitlistSignup(models.Model):
    """Inscription à la liste d'attente d'une boutique en préparation.

    Quand un visiteur arrive sur <slug>.jappesi.sn et que la boutique n'a
    encore aucun produit actif, il voit une page "Boutique en préparation"
    avec un formulaire pour être notifié de l'ouverture. Chaque soumission
    crée une entrée WaitlistSignup, et un SMS est envoyé au commerçant pour
    qu'il sache qu'un client potentiel attend.

    Le couple (shop, phone) est unique pour éviter les doublons d'un même
    visiteur qui re-soumet plusieurs fois.
    """

    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="waitlist_signups",
    )
    name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(
        max_length=20,
        help_text="Numéro WhatsApp normalisé E.164 (+221XXXXXXXXX).",
    )
    email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    # Permet plus tard une fonction "Notifier la waitlist du lancement"
    # qui ne renotifie pas ceux qui l'ont déjà été.
    notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Inscription liste d'attente"
        verbose_name_plural = "Inscriptions liste d'attente"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("shop", "phone"),
                name="uniq_waitlist_shop_phone",
            ),
        ]

    def __str__(self):
        return f"{self.phone} → {self.shop.slug}"
