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
    """Utilisateur Jayma — peut être client, commerçant ou admin."""

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
