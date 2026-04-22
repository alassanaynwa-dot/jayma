"""Stats plateforme pour le dashboard admin owner."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone
from django.utils.formats import date_format

from commissions.models import Commission
from orders.models import Order, OrderItem
from shops.models import Shop, ShopRequest


def get_platform_stats() -> dict:
    """Home dashboard : KPIs principaux + données pour graphiques."""
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
        .annotate(orders_count=Count("orders"))
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

        # Graphiques
        "gmv_series": get_gmv_timeseries(days=30),
        "top_categories": get_top_categories(limit=6),
    }


def get_gmv_timeseries(days: int = 30) -> list[dict]:
    """Série journalière GMV + commission + orders sur les N derniers jours."""
    now = timezone.now()
    start = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)

    qs = (
        Order.objects
        .filter(
            created_at__gte=start,
            payment_status=Order.PaymentStatus.PAID,
        )
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(
            gmv=Sum("total_xof"),
            commission=Sum("commission_xof"),
            orders=Count("id"),
        )
    )
    by_day = {row["day"]: row for row in qs}

    series = []
    for i in range(days):
        d = (start + timedelta(days=i)).date()
        row = by_day.get(d)
        series.append({
            "date": d.isoformat(),
            "label": d.strftime("%d/%m"),
            "gmv": (row["gmv"] or 0) if row else 0,
            "commission": (row["commission"] or 0) if row else 0,
            "orders": (row["orders"] or 0) if row else 0,
        })
    return series


def get_top_categories(limit: int = 10) -> list[dict]:
    """Top catégories cross-boutique par revenu (via OrderItem → Product → Category)."""
    qs = (
        OrderItem.objects
        .filter(
            order__payment_status=Order.PaymentStatus.PAID,
            product__category__isnull=False,
        )
        .values(
            "product__category__name",
            "product__category__slug",
        )
        .annotate(
            revenue=Sum("unit_price_xof"),
            units_sold=Sum("quantity"),
        )
        .order_by("-revenue")[:limit]
    )
    return [
        {
            "name": row["product__category__name"],
            "slug": row["product__category__slug"],
            "revenue": row["revenue"] or 0,
            "units_sold": row["units_sold"] or 0,
        }
        for row in qs
    ]


def get_monthly_summary(months: int = 6) -> list[dict]:
    """Récap mensuel sur les N derniers mois (mois courant inclus, descendant)."""
    now = timezone.now()
    first_of_current = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # reculer jusqu'au 1er jour du plus ancien mois voulu
    start = first_of_current
    for _ in range(months - 1):
        start = (start - timedelta(days=1)).replace(day=1)

    qs = (
        Order.objects
        .filter(created_at__gte=start, payment_status=Order.PaymentStatus.PAID)
        .annotate(m=TruncMonth("created_at"))
        .values("m")
        .annotate(
            gmv=Sum("total_xof"),
            commission=Sum("commission_xof"),
            orders=Count("id"),
            active_shops=Count("shop", distinct=True),
        )
    )
    by_month = {row["m"].date(): row for row in qs}

    result = []
    cursor = first_of_current
    for _ in range(months):
        d = cursor.date()
        row = by_month.get(d)
        result.append({
            "month": d,
            "label": date_format(cursor, format="F Y", use_l10n=True),
            "gmv": (row["gmv"] or 0) if row else 0,
            "commission": (row["commission"] or 0) if row else 0,
            "orders": (row["orders"] or 0) if row else 0,
            "active_shops": (row["active_shops"] or 0) if row else 0,
        })
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    return result
