"""Calculs de stats pour le dashboard commerçant."""
from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from orders.models import Order


def get_dashboard_stats(shop) -> dict:
    """Retourne les stats principales d'un shop pour l'accueil du dashboard."""
    now = timezone.now()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    previous_month_end = start_of_month - timedelta(seconds=1)
    previous_month_start = previous_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    products = shop.products.all()
    total_products = products.filter(is_active=True).count()
    low_stock = products.filter(is_active=True, track_stock=True, stock__lte=5).count()

    orders_qs = Order.objects.filter(shop=shop)
    orders_this_month = orders_qs.filter(created_at__gte=start_of_month)
    orders_prev_month = orders_qs.filter(
        created_at__gte=previous_month_start,
        created_at__lt=start_of_month,
    )

    revenue_this_month = orders_this_month.filter(
        payment_status=Order.PaymentStatus.PAID
    ).aggregate(total=Sum("merchant_amount_xof"))["total"] or 0

    revenue_prev_month = orders_prev_month.filter(
        payment_status=Order.PaymentStatus.PAID
    ).aggregate(total=Sum("merchant_amount_xof"))["total"] or 0

    return {
        "total_products": total_products,
        "low_stock": low_stock,
        "orders_month": orders_this_month.count(),
        "orders_pending": orders_qs.filter(status=Order.Status.PENDING).count(),
        "revenue_month": revenue_this_month,
        "revenue_prev": revenue_prev_month,
        "revenue_delta_pct": _delta_pct(revenue_prev_month, revenue_this_month),
        "last_orders": orders_qs.order_by("-created_at")[:5],
    }


def _delta_pct(previous: int, current: int) -> int | None:
    if previous == 0:
        return None
    return round(((current - previous) / previous) * 100)
