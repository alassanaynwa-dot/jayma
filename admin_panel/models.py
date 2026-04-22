"""Journal d'audit des actions plateforme (traçabilité)."""
from django.conf import settings
from django.db import models


class AdminAction(models.Model):
    """
    Enregistrement immuable d'une action effectuée par un admin plateforme.

    On stocke l'acteur, l'action, éventuellement la cible (via un triplet
    content_type-libre + object_repr) et un payload libre pour le contexte
    métier. Pas de relations GenericForeignKey pour rester simple à lire.
    """

    class Action(models.TextChoices):
        SHOP_APPROVED = "shop.approved", "Boutique approuvée"
        SHOP_REJECTED = "shop.rejected", "Demande rejetée"
        SHOP_TOGGLED = "shop.toggled", "Boutique activée/désactivée"
        SHOP_COMMISSION_UPDATED = "shop.commission_updated", "Commission modifiée"
        MERCHANT_PASSWORD_RESET = "merchant.password_reset", "Mot de passe commerçant réinitialisé"
        REVIEW_MODERATED = "review.moderated", "Avis modéré"
        COMMISSION_PAID = "commission.paid", "Commission marquée payée"
        PRODUCT_TOGGLED = "product.toggled", "Produit activé/désactivé"
        USER_TOGGLED = "user.toggled", "Utilisateur bloqué/débloqué"
        MERCHANT_REENGAGE_SENT = "merchant.reengage_sent", "Relance zombie envoyée"
        SETTINGS_UPDATED = "settings.updated", "Réglages plateforme modifiés"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="admin_actions",
    )
    action = models.CharField(max_length=50, choices=Action.choices, db_index=True)
    target_type = models.CharField(
        max_length=50, blank=True,
        help_text="Nom du modèle ciblé (ex. Shop, ProductReview).",
    )
    target_id = models.CharField(
        max_length=50, blank=True,
        help_text="ID ou référence de l'objet ciblé.",
    )
    target_repr = models.CharField(
        max_length=200, blank=True,
        help_text="Représentation lisible (nom boutique, référence commande…).",
    )
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Action admin"
        verbose_name_plural = "Journal d'audit"
        ordering = ("-created_at",)

    def __str__(self):
        who = self.actor.username if self.actor else "?"
        return f"{who} · {self.get_action_display()} · {self.target_repr or '-'}"
