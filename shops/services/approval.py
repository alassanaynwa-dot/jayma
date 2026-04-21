"""
Service d'approbation d'une demande de boutique.

Règle : transaction atomique. Soit la demande est approuvée et le
User+Shop sont créés, soit rien ne change.
"""
import secrets
import logging
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from shops.models import Shop, ShopRequest

logger = logging.getLogger("jayma")

User = get_user_model()


class ApprovalError(Exception):
    """Erreur métier lors de l'approbation (slug pris, user conflit, etc.)."""


@transaction.atomic
def approve_shop_request(shop_request: ShopRequest, reviewed_by) -> tuple[Shop, str | None]:
    """
    Approuve une demande et crée le User commerçant + Shop associés.

    Retourne (shop, temp_password). temp_password est None si le User
    existait déjà (il garde ses identifiants actuels).
    Lève ApprovalError en cas de problème métier.
    """
    if shop_request.status == ShopRequest.Status.APPROVED:
        raise ApprovalError("Cette demande est déjà approuvée.")

    # Vérif slug toujours libre (course condition possible)
    if Shop.objects.filter(slug=shop_request.desired_slug).exists():
        raise ApprovalError(
            f"Le slug '{shop_request.desired_slug}' a été pris entre-temps."
        )

    # Créer ou récupérer le User commerçant (par email)
    user, created = User.objects.get_or_create(
        email=shop_request.email,
        defaults={
            "username": _build_username(shop_request),
            "phone": shop_request.phone,
            "city": shop_request.city,
            "role": User.Role.MERCHANT,
            "first_name": shop_request.full_name.split(" ")[0] if shop_request.full_name else "",
            "last_name": " ".join(shop_request.full_name.split(" ")[1:]) if shop_request.full_name else "",
        },
    )

    # User déjà existant avec un autre Shop → on refuse
    if not created and hasattr(user, "shop"):
        raise ApprovalError(
            f"L'utilisateur {user.email} a déjà une boutique ({user.shop.slug})."
        )

    temp_password = None
    if created:
        temp_password = secrets.token_urlsafe(10)
        user.set_password(temp_password)
        user.role = User.Role.MERCHANT
        user.save()

    # Créer la boutique
    shop = Shop.objects.create(
        owner=user,
        name=shop_request.shop_name,
        slug=shop_request.desired_slug,
        description=shop_request.description,
        phone=shop_request.phone,
        whatsapp=shop_request.phone,
        city=shop_request.city,
        is_approved=True,
        is_active=True,
    )

    # Marquer la demande comme approuvée
    shop_request.status = ShopRequest.Status.APPROVED
    shop_request.reviewed_by = reviewed_by
    shop_request.reviewed_at = timezone.now()
    shop_request.save()

    logger.info("ShopRequest %s approuvée → Shop %s créé.", shop_request.pk, shop.slug)
    return shop, temp_password


def _build_username(shop_request: ShopRequest) -> str:
    """Génère un username unique à partir du slug désiré."""
    base = shop_request.desired_slug[:30]
    candidate = base
    i = 1
    while User.objects.filter(username=candidate).exists():
        i += 1
        candidate = f"{base}{i}"
    return candidate
