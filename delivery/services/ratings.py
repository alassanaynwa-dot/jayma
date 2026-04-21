"""Statistiques de notation pour les livreurs."""
from django.db.models import Avg, Count

from orders.models import Order

from ..models import Courier


def get_courier_rating_stats(courier: Courier) -> dict:
    """Retourne moyenne, compte et répartition des notes d'un livreur."""
    rated = Order.objects.filter(
        courier=courier,
        delivery_rating__isnull=False,
    )
    agg = rated.aggregate(avg=Avg("delivery_rating"), total=Count("id"))
    distribution = {i: 0 for i in range(1, 6)}
    for row in rated.values("delivery_rating").annotate(n=Count("id")):
        distribution[row["delivery_rating"]] = row["n"]

    avg = agg["avg"] or 0
    total = agg["total"] or 0
    return {
        "average": round(avg, 1) if total else None,
        "total": total,
        "distribution": distribution,  # {1: 0, 2: 1, 3: 3, 4: 12, 5: 48}
    }
