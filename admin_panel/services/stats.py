"""Stats plateforme pour le dashboard admin owner."""
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.utils import timezone

from commissions.models import Commission
from orders.models import Order
from shops.models import Shop, ShopRequest


def get_platform_stats() -> dict:
    now = timezone.now()
    start_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    User = get_user_model()

    total_shops = Shop.objects.filter(is_approved=True).count()
    total_merchants = User.objects.filter(role=User.Role.MERCHANT).count()
    pending_requests = ShopRequest.objects.filter(status=ShopRequest.Status.PENDING).count()

    paid_orders_month = Order.objects.filter(
        created_at__gte=start_month,
        payment_status=Order.PaymentStatus.PAID,
    )
    gmv_month = paid_orders_month.aggregate(t=Sum("total_xof"))["t"] or 0
    commissions_month = paid_orders_month.aggregate(t=Sum("commission_xof"))["t"] or 0

    commissions_to_payout = Commission.objects.filter(is_paid=False).aggregate(
        total=Sum("merchant_amount_xof"),
        count=Count("id"),
    )

    top_shops = (
        Shop.objects
        .filter(is_approved=True)
        .annotate(orders_count=Count("orders", filter=None))
        .order_by("-orders_count")[:5]
    )

    return {
        "total_shops": total_shops,
        "total_merchants": total_merchants,
        "pending_requests": pending_requests,
        "gmv_month": gmv_month,
        "commissions_month": commissions_month,
        "orders_month": paid_orders_month.count(),
        "payout_total": commissions_to_payout["total"] or 0,
        "payout_count": commissions_to_payout["count"] or 0,
        "top_shops": top_shops,
        "recent_requests": ShopRequest.objects.filter(
            status=ShopRequest.Status.PENDING
        ).order_by("-created_at")[:5],
        "recent_orders": Order.objects.select_related("shop").order_by("-created_at")[:8],
    }
