"""
Agrégation des clients d'une boutique.

Dans Jappesi, un "client" n'a pas de compte. On les identifie par leur
numéro de téléphone (client_phone), qui est obligatoire au checkout.
On agrège donc les Orders par client_phone pour obtenir une vue client.
"""
from dataclasses import dataclass
from typing import Iterable

from django.db.models import Count, Max, Min, Sum

from ..models import Order


@dataclass
class ClientRow:
    """Une ligne de la liste clients agrégée depuis les commandes."""
    phone: str
    last_name: str
    last_city: str
    orders_count: int
    total_spent: int
    paid_count: int
    first_order_at: object
    last_order_at: object


def list_clients(shop, q: str = "") -> list[ClientRow]:
    """Retourne la liste des clients agrégés (un par téléphone)."""
    orders = Order.objects.filter(shop=shop)
    if q:
        from django.db.models import Q
        orders = orders.filter(
            Q(client_name__icontains=q) | Q(client_phone__icontains=q) | Q(client_email__icontains=q)
        )

    grouped = (
        orders.values("client_phone")
        .annotate(
            orders_count=Count("id"),
            total_spent=Sum("total_xof"),
            paid_count=Count("id", filter=_paid_filter()),
            first_order_at=Min("created_at"),
            last_order_at=Max("created_at"),
        )
        .order_by("-last_order_at")
    )

    rows = []
    for g in grouped:
        # Dernière commande du client pour récupérer nom/ville à jour
        last = orders.filter(client_phone=g["client_phone"]).order_by("-created_at").first()
        rows.append(ClientRow(
            phone=g["client_phone"],
            last_name=last.client_name if last else "",
            last_city=last.client_city if last else "",
            orders_count=g["orders_count"],
            total_spent=g["total_spent"] or 0,
            paid_count=g["paid_count"] or 0,
            first_order_at=g["first_order_at"],
            last_order_at=g["last_order_at"],
        ))
    return rows


def _paid_filter():
    from django.db.models import Q
    return Q(payment_status=Order.PaymentStatus.PAID)


def get_client_orders(shop, phone: str) -> Iterable[Order]:
    """Toutes les commandes d'un client donné (par téléphone) pour une boutique."""
    return (
        Order.objects
        .filter(shop=shop, client_phone=phone)
        .prefetch_related("items")
        .order_by("-created_at")
    )
