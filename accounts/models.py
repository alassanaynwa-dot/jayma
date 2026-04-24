"""
Modèles accounts — utilisateur unique pour tous les rôles (client, commerçant, admin).

Un seul modèle User permet à un même compte d'être client chez plusieurs
boutiques ET commerçant sur la sienne.
"""
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models


# Numéro de téléphone sénégalais : +221 77 xxx xx xx ou 77xxxxxxx
phone_validator = RegexValidator(
    regex=r"^(\+221)?[37][0-9]{8}$",
    message="Numéro de téléphone sénégalais invalide.",
)


class User(AbstractUser):
    """Utilisateur Jappesi — peut être client, commerçant ou admin."""

    class Role(models.TextChoices):
        CLIENT = "client", "Client"
        MERCHANT = "merchant", "Commerçant"
        ADMIN = "admin", "Admin plateforme"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CLIENT,
        db_index=True,
    )
    phone = models.CharField(
        max_length=20,
        validators=[phone_validator],
        help_text="Téléphone sénégalais — obligatoire.",
    )
    city = models.CharField(
        max_length=100,
        blank=True,
        help_text="Dakar, Thiès, Saint-Louis, etc.",
    )
    phone_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    @property
    def is_merchant(self) -> bool:
        return self.role == self.Role.MERCHANT

    @property
    def is_platform_admin(self) -> bool:
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def is_client(self) -> bool:
        return self.role == self.Role.CLIENT


class ClientAddress(models.Model):
    """Adresse sauvegardée d'un client (carnet d'adresses)."""
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="addresses",
    )
    label = models.CharField(
        max_length=40,
        help_text="Ex : Maison, Bureau, Chez maman",
    )
    address = models.TextField()
    city = models.CharField(max_length=100)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Adresse client"
        verbose_name_plural = "Adresses clients"
        ordering = ("-is_default", "-created_at")

    def __str__(self):
        return f"{self.label} — {self.city}"

    def save(self, *args, **kwargs):
        # Si on marque celle-ci par défaut, enlever le flag des autres
        if self.is_default:
            ClientAddress.objects.filter(
                user=self.user, is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class OTPToken(models.Model):
    """
    Code OTP à 4 chiffres envoyé par SMS pour l'auth client.
    Stockage DB plutôt que cache (audit + max 1 actif par phone).
    """
    phone = models.CharField(max_length=20, db_index=True)
    code = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Code OTP"
        verbose_name_plural = "Codes OTP"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["phone", "-created_at"])]

    def __str__(self):
        return f"{self.phone} → {self.code} ({'utilisé' if self.consumed_at else 'actif'})"
