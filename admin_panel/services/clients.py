"""Agrégation des clients cross-boutique pour la vue admin.

Regroupe les commandes par téléphone client et retourne la liste des
clients top spenders avec leur dernier nom connu (snapshot pris sur la
commande la plus récente).

Extrait de admin_panel/views.py pour alléger la vue et permettre les
tests unitaires sans monter une Client HTTP.
"""
from django.db.models import Count, Q, Sum
from django.db.models.aggregates import Max
from django.db.models.functions import Coalesce

from orders.models import Order


def list_top_clients(q: str = "", limit: int = 200) -> list[dict]:
    """Retourne les clients cross-boutique groupés par téléphone.

    - Filtre optionnel `q` sur nom / téléphone / email
    - Trie par total dépensé décroissant
    - Limite par défaut : 200 (pas de pagination dans le dashboard pour
      l'instant — quand on dépassera 200 clients distincts, ajouter)

    Chaque dict contient :
        phone, name, orders_count, shops_count, total_spent,
        paid_count, last_at
    """
    orders_qs = Order.objects.all()
    if q:
        orders_qs = orders_qs.filter(
            Q(client_name__icontains=q)
            | Q(client_phone__icontains=q)
            | Q(client_email__icontains=q)
        )

    # 1. Agrégation en 1 query : compte, somme, max date par téléphone.
    grouped = list(
        orders_qs.values("client_phone")
        .annotate(
            orders_count=Count("id"),
            shops_count=Count("shop", distinct=True),
            total_spent=Coalesce(Sum("total_xof"), 0),
            paid_count=Count("id", filter=Q(payment_status=Order.PaymentStatus.PAID)),
            last_at=Max("created_at"),
        )
        .order_by("-total_spent")[:limit]
    )

    # 2. Récupère le dernier client_name par téléphone en 1 query (DISTINCT ON).
    #    Évite le N+1 (anciennement 1 SELECT/client pour son dernier order).
    phones = [g["client_phone"] for g in grouped]
    last_names = {}
    if phones:
        last_orders = (
            Order.objects.filter(client_phone__in=phones)
            .order_by("client_phone", "-created_at")
            .distinct("client_phone")  # Postgres-spécifique
            .values_list("client_phone", "client_name")
        )
        last_names = dict(last_orders)

    return [
        {
            "phone": g["client_phone"],
            "name": last_names.get(g["client_phone"], ""),
            "orders_count": g["orders_count"],
            "shops_count": g["shops_count"],
            "total_spent": g["total_spent"],
            "paid_count": g["paid_count"],
            "last_at": g["last_at"],
        }
        for g in grouped
    ]
