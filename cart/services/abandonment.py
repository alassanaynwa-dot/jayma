"""Service de tracking des paniers abandonnés."""
import logging

from django.utils import timezone

from ..models import AbandonedCart
from .cart import Cart

logger = logging.getLogger("jayma")


def snapshot_cart(request, shop, client_phone: str, client_name: str = "") -> AbandonedCart | None:
    """
    Crée/met à jour un AbandonedCart en DB depuis le panier session courant.
    Appelé depuis la vue checkout quand on connaît le phone du client.
    """
    phone = (client_phone or "").replace(" ", "").strip()
    if not phone:
        return None

    cart = Cart(request)
    if len(cart) == 0:
        # Panier vide → pas d'abandon à tracker, et on supprime tout snapshot existant
        AbandonedCart.objects.filter(shop=shop, client_phone=phone).delete()
        return None

    items_json = list(cart)  # [{product_id, name, unit_price, quantity, line_total}]

    ac, _ = AbandonedCart.objects.update_or_create(
        shop=shop, client_phone=phone,
        defaults={
            "client_name": client_name[:100],
            "items_json": items_json,
            "total_xof": cart.total_xof,
            "reminded_at": None,    # on reset pour pouvoir relancer si le panier change
            "recovered_at": None,
        },
    )
    return ac


def mark_recovered(shop, client_phone: str) -> None:
    """Appelé après création d'une Order — évite une relance inutile."""
    phone = (client_phone or "").replace(" ", "").strip()
    if not phone:
        return
    AbandonedCart.objects.filter(
        shop=shop, client_phone=phone, recovered_at__isnull=True,
    ).update(recovered_at=timezone.now())
