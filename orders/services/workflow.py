"""
State machine des commandes + notifications SMS liées aux transitions.

Transitions autorisées :
    pending    → confirmed | cancelled
    confirmed  → shipped | cancelled
    shipped    → delivered | disputed
    delivered  → (final)
    cancelled  → (final)
    disputed   → delivered | cancelled
"""
from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from notifications.services.sms import send_sms

from ..models import Order

logger = logging.getLogger("jayma")


ALLOWED_TRANSITIONS = {
    Order.Status.PENDING:   {Order.Status.CONFIRMED, Order.Status.CANCELLED},
    Order.Status.CONFIRMED: {Order.Status.SHIPPED,   Order.Status.CANCELLED},
    Order.Status.SHIPPED:   {Order.Status.DELIVERED, Order.Status.DISPUTED},
    Order.Status.DELIVERED: set(),
    Order.Status.CANCELLED: set(),
    Order.Status.DISPUTED:  {Order.Status.DELIVERED, Order.Status.CANCELLED},
}


class TransitionError(Exception):
    """Transition interdite par la state machine."""


@transaction.atomic
def transition_order(order: Order, new_status: str, notify: bool = True) -> Order:
    """Fait passer une commande à un nouveau statut, en notifiant le client."""
    if new_status not in ALLOWED_TRANSITIONS.get(order.status, set()):
        raise TransitionError(
            f"Transition interdite : {order.get_status_display()} → {new_status}"
        )

    order.status = new_status
    if new_status == Order.Status.DELIVERED:
        order.delivered_at = timezone.now()
        # Si paiement cash, la livraison = paiement effectif
        if order.payment_method == Order.PaymentMethod.CASH:
            order.payment_status = Order.PaymentStatus.PAID
            order.paid_at = timezone.now()
    order.save()

    if notify:
        _notify_client(order)

    logger.info("Order %s → %s", order.reference, new_status)
    return order


def _notify_client(order: Order) -> None:
    """Envoie un SMS au client selon le nouveau statut (best-effort)."""
    from django.conf import settings
    root = settings.JAYMA_ROOT_DOMAIN

    rating_suffix = ""
    if order.status == Order.Status.DELIVERED and order.courier:
        rating_suffix = f" Note ta livraison : {order.shop.slug}.{root}/commander/{order.reference}/noter/"

    # Pour tous les statuts en cours, on inclut le lien de suivi public
    tracking_link = (
        f" Suivi : {order.shop.slug}.{root}/suivi/?ref={order.reference}"
        f"&phone={order.client_phone}"
        if order.status in (Order.Status.CONFIRMED, Order.Status.SHIPPED) else ""
    )

    templates = {
        Order.Status.CONFIRMED:
            f"Ta commande {order.reference} chez {order.shop.name} est confirmee ! "
            f"Total {order.total_xof} XOF. Merci." + tracking_link,
        Order.Status.SHIPPED:
            f"Ta commande {order.reference} est en route ! "
            + (f"Suivi: {order.tracking_number}. " if order.tracking_number else "")
            + f"Livraison a {order.client_city}." + tracking_link,
        Order.Status.DELIVERED:
            f"Ta commande {order.reference} a bien ete livree. "
            f"Merci d'avoir choisi {order.shop.name} !" + rating_suffix,
        Order.Status.CANCELLED:
            f"Ta commande {order.reference} a ete annulee. "
            f"Contacte {order.shop.name} au {order.shop.phone} pour plus d'infos.",
    }
    text = templates.get(order.status)
    if not text:
        return

    try:
        send_sms(order.client_phone, text)
    except Exception:
        logger.exception("Échec SMS client pour order %s", order.reference)
