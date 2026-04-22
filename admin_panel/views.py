"""Vues admin.jayma.sn — dashboard owner de la plateforme."""
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db.models import Count, Max, Q, Sum
from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from commissions.models import Commission
from core.models import PlatformSettings
from core.tasks import send_merchant_welcome
from delivery.models import Courier
from notifications.models import NotificationLog
from orders.models import Order
from payments.models import WebhookEvent
from products.models import Category, Product, ProductReview
from shops.models import Shop, ShopRequest
from shops.services.approval import ApprovalError, approve_shop_request

from .decorators import platform_admin_required
from .models import AdminAction
from .services.audit import log_admin_action
from .services.password_reset import reset_merchant_password
from .services.stats import get_monthly_summary, get_platform_stats


@platform_admin_required
def admin_home(request):
    return render(request, "admin_panel/home.html", {"stats": get_platform_stats()})


# ============ DEMANDES ============

@platform_admin_required
def admin_requests(request):
    requests_qs = ShopRequest.objects.select_related("reviewed_by").order_by("-created_at")
    status = request.GET.get("status", "pending")
    if status:
        requests_qs = requests_qs.filter(status=status)
    return render(request, "admin_panel/requests.html", {
        "shop_requests": requests_qs, "status": status,
    })


@platform_admin_required
@require_POST
def admin_request_approve(request, pk):
    sr = get_object_or_404(ShopRequest, pk=pk)
    try:
        shop, temp_password = approve_shop_request(sr, reviewed_by=request.user)
    except ApprovalError as exc:
        messages.error(request, str(exc))
        return redirect("admin_panel:requests")
    try:
        send_merchant_welcome.delay(shop.pk, temp_password)
    except Exception:
        send_merchant_welcome(shop.pk, temp_password)
    log_admin_action(
        actor=request.user,
        action=AdminAction.Action.SHOP_APPROVED,
        target=shop,
        meta={"request_id": sr.pk, "commission_rate": str(shop.commission_rate)},
    )
    messages.success(request, f"Boutique « {shop.name} » créée — email + SMS envoyés au commerçant.")
    return redirect("admin_panel:requests")


@platform_admin_required
@require_POST
def admin_request_reject(request, pk):
    sr = get_object_or_404(ShopRequest, pk=pk)
    sr.status = ShopRequest.Status.REJECTED
    sr.reviewed_by = request.user
    sr.reviewed_at = timezone.now()
    sr.admin_notes = request.POST.get("admin_notes", "")
    sr.save()
    log_admin_action(
        actor=request.user,
        action=AdminAction.Action.SHOP_REJECTED,
        target=sr,
        target_repr=f"{sr.shop_name} ({sr.desired_slug})",
        meta={"reason": sr.admin_notes[:200]},
    )
    messages.info(request, "Demande rejetée.")
    return redirect("admin_panel:requests")


# ============ BOUTIQUES ============

@platform_admin_required
def admin_shops(request):
    q = (request.GET.get("q") or "").strip()
    shops = (
        Shop.objects.select_related("owner")
        .annotate(
            orders_count=Count("orders"),
            revenue=Sum("orders__total_xof", filter=Q(orders__payment_status=Order.PaymentStatus.PAID)),
        )
        .order_by("-created_at")
    )
    if q:
        shops = shops.filter(
            Q(name__icontains=q) | Q(slug__icontains=q) | Q(owner__email__icontains=q)
        )
    return render(request, "admin_panel/shops.html", {"shops": shops, "q": q})


@platform_admin_required
def admin_shop_detail(request, pk):
    """Fiche complète d'une boutique : stats, produits, commandes, livreurs, actions."""
    shop = get_object_or_404(Shop.objects.select_related("owner"), pk=pk)

    now = timezone.now()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    orders_qs = shop.orders.all()
    orders_month = orders_qs.filter(created_at__gte=start_of_month)
    paid_month = orders_month.filter(payment_status=Order.PaymentStatus.PAID)

    stats = {
        "total_products": shop.products.filter(is_active=True).count(),
        "total_orders": orders_qs.count(),
        "orders_pending": orders_qs.filter(status=Order.Status.PENDING).count(),
        "orders_month": orders_month.count(),
        "revenue_month": paid_month.aggregate(t=Sum("total_xof"))["t"] or 0,
        "commission_month": paid_month.aggregate(t=Sum("commission_xof"))["t"] or 0,
        "gmv_total": orders_qs.filter(payment_status=Order.PaymentStatus.PAID).aggregate(
            t=Sum("total_xof")
        )["t"] or 0,
        "commissions_due": Commission.objects.filter(shop=shop, is_paid=False).aggregate(
            m=Sum("merchant_amount_xof"),
        )["m"] or 0,
    }

    last_orders = orders_qs.order_by("-created_at")[:10]
    recent_products = shop.products.order_by("-created_at")[:8]
    couriers = shop.couriers.all()[:10]

    return render(request, "admin_panel/shop_detail.html", {
        "shop": shop,
        "stats": stats,
        "last_orders": last_orders,
        "recent_products": recent_products,
        "couriers": couriers,
    })


@platform_admin_required
@require_POST
def admin_shop_toggle_active(request, pk):
    shop = get_object_or_404(Shop, pk=pk)
    shop.is_active = not shop.is_active
    shop.save(update_fields=["is_active", "updated_at"])
    state = "activée" if shop.is_active else "désactivée"
    log_admin_action(
        actor=request.user,
        action=AdminAction.Action.SHOP_TOGGLED,
        target=shop,
        meta={"is_active": shop.is_active},
    )
    messages.success(request, f"Boutique « {shop.name} » {state}.")
    return redirect("admin_panel:shop_detail", pk=shop.pk)


@platform_admin_required
@require_POST
def admin_shop_update_commission(request, pk):
    shop = get_object_or_404(Shop, pk=pk)
    raw = (request.POST.get("commission_rate") or "").replace(",", ".").strip()
    try:
        rate = Decimal(raw)
    except (InvalidOperation, ValueError):
        messages.error(request, "Taux de commission invalide.")
        return redirect("admin_panel:shop_detail", pk=shop.pk)
    if not (0 <= rate <= 50):
        messages.error(request, "Le taux doit être entre 0 et 50%.")
        return redirect("admin_panel:shop_detail", pk=shop.pk)

    old_rate = shop.commission_rate
    shop.commission_rate = rate
    shop.save(update_fields=["commission_rate", "updated_at"])
    log_admin_action(
        actor=request.user,
        action=AdminAction.Action.SHOP_COMMISSION_UPDATED,
        target=shop,
        meta={"old_rate": str(old_rate), "new_rate": str(rate)},
    )
    messages.success(request, f"Commission de « {shop.name} » : {old_rate}% → {rate}%.")
    return redirect("admin_panel:shop_detail", pk=shop.pk)


@platform_admin_required
@require_POST
def admin_shop_reset_password(request, pk):
    shop = get_object_or_404(Shop, pk=pk)
    new_pw = reset_merchant_password(shop.owner)
    log_admin_action(
        actor=request.user,
        action=AdminAction.Action.MERCHANT_PASSWORD_RESET,
        target=shop,
        target_repr=f"{shop.name} ({shop.owner.email})",
    )
    messages.success(
        request,
        f"Nouveau mot de passe envoyé à {shop.owner.phone} et {shop.owner.email}. "
        f"(Temporaire, affiché ici pour copie : {new_pw})"
    )
    return redirect("admin_panel:shop_detail", pk=shop.pk)


# ============ COMMANDES (cross-boutique) ============

@platform_admin_required
def admin_orders(request):
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    shop_slug = (request.GET.get("shop") or "").strip()

    orders = Order.objects.select_related("shop").prefetch_related("items")

    if q:
        orders = orders.filter(
            Q(reference__icontains=q)
            | Q(client_name__icontains=q)
            | Q(client_phone__icontains=q)
        )
    if status:
        orders = orders.filter(status=status)
    if shop_slug:
        orders = orders.filter(shop__slug=shop_slug)

    orders = orders.order_by("-created_at")[:200]

    return render(request, "admin_panel/orders_list.html", {
        "orders": orders,
        "q": q, "status": status, "shop_slug": shop_slug,
        "statuses": Order.Status.choices,
        "shops": Shop.objects.filter(is_approved=True).order_by("name"),
    })


@platform_admin_required
def admin_order_detail(request, reference):
    order = get_object_or_404(
        Order.objects.select_related("shop", "courier", "shop__owner").prefetch_related("items__product", "payments"),
        reference=reference,
    )
    commission = Commission.objects.filter(order=order).first()
    return render(request, "admin_panel/order_detail.html", {
        "order": order, "commission": commission,
    })


# ============ CLIENTS ============

@platform_admin_required
def admin_clients(request):
    q = (request.GET.get("q") or "").strip()

    orders_qs = Order.objects.all()
    if q:
        orders_qs = orders_qs.filter(
            Q(client_name__icontains=q)
            | Q(client_phone__icontains=q)
            | Q(client_email__icontains=q)
        )

    grouped = (
        orders_qs.values("client_phone")
        .annotate(
            orders_count=Count("id"),
            shops_count=Count("shop", distinct=True),
            total_spent=Sum("total_xof"),
            paid_count=Count("id", filter=Q(payment_status=Order.PaymentStatus.PAID)),
        )
        .order_by("-total_spent")[:200]
    )

    rows = []
    for g in grouped:
        last = orders_qs.filter(client_phone=g["client_phone"]).order_by("-created_at").first()
        rows.append({
            "phone": g["client_phone"],
            "name": last.client_name if last else "",
            "orders_count": g["orders_count"],
            "shops_count": g["shops_count"],
            "total_spent": g["total_spent"] or 0,
            "paid_count": g["paid_count"] or 0,
            "last_at": last.created_at if last else None,
        })

    return render(request, "admin_panel/clients_list.html", {
        "clients": rows, "q": q,
    })


# ============ AVIS PRODUITS ============

@platform_admin_required
def admin_reviews(request):
    filter_state = (request.GET.get("state") or "all").strip()
    qs = ProductReview.objects.select_related("product", "product__shop").order_by("-created_at")
    if filter_state == "approved":
        qs = qs.filter(is_approved=True)
    elif filter_state == "hidden":
        qs = qs.filter(is_approved=False)

    return render(request, "admin_panel/reviews_list.html", {
        "reviews": qs[:200],
        "state": filter_state,
    })


@platform_admin_required
@require_POST
def admin_review_toggle_approved(request, pk):
    review = get_object_or_404(ProductReview, pk=pk)
    review.is_approved = not review.is_approved
    review.save(update_fields=["is_approved"])
    state = "affiché" if review.is_approved else "masqué"
    log_admin_action(
        actor=request.user,
        action=AdminAction.Action.REVIEW_MODERATED,
        target=review,
        target_repr=f"{review.rating}★ sur {review.product.name}",
        meta={"is_approved": review.is_approved},
    )
    messages.success(request, f"Avis {state}.")
    return redirect(request.META.get("HTTP_REFERER") or "admin_panel:reviews")


# ============ COMMISSIONS ============

@platform_admin_required
def admin_commissions(request):
    filter_state = request.GET.get("state", "unpaid")
    qs = Commission.objects.select_related("order", "shop").order_by("-created_at")
    if filter_state == "unpaid":
        qs = qs.filter(is_paid=False)
    elif filter_state == "paid":
        qs = qs.filter(is_paid=True)

    total_unpaid = Commission.objects.filter(is_paid=False).aggregate(
        total=Sum("merchant_amount_xof"),
        commission=Sum("commission_xof"),
    )
    return render(request, "admin_panel/commissions.html", {
        "commissions": qs[:200],
        "state": filter_state,
        "total_unpaid_merchant": total_unpaid["total"] or 0,
        "total_commission": total_unpaid["commission"] or 0,
    })


@platform_admin_required
@require_POST
def admin_commission_mark_paid(request, pk):
    c = get_object_or_404(Commission, pk=pk)
    c.is_paid = True
    c.paid_at = timezone.now()
    c.payout_reference = request.POST.get("payout_reference", "").strip()[:100]
    c.save()
    log_admin_action(
        actor=request.user,
        action=AdminAction.Action.COMMISSION_PAID,
        target=c,
        target_repr=f"{c.shop.name} · {c.order.reference}",
        meta={"amount_xof": c.merchant_amount_xof, "payout_reference": c.payout_reference},
    )
    messages.success(request, f"Reversement pour {c.shop.name} marqué comme payé.")
    return redirect("admin_panel:commissions")


@platform_admin_required
def admin_commissions_export_csv(request):
    """Export CSV streamé des commissions (filtrable par ?state=unpaid|paid|all)."""
    import csv
    from django.http import StreamingHttpResponse

    filter_state = request.GET.get("state", "unpaid")
    qs = Commission.objects.select_related("order", "shop", "shop__owner").order_by("-created_at")
    if filter_state == "unpaid":
        qs = qs.filter(is_paid=False)
    elif filter_state == "paid":
        qs = qs.filter(is_paid=True)

    class Echo:
        """File-like qui yield au lieu d'écrire — pour streaming."""
        def write(self, value):
            return value

    writer = csv.writer(Echo())
    columns = [
        "Référence commande", "Boutique", "Slug", "Commerçant", "Email",
        "Date", "Vente XOF", "Taux %", "Commission XOF", "À reverser XOF",
        "Reversé", "Date reversement", "Référence virement",
    ]

    def rows():
        yield writer.writerow(columns)
        for c in qs.iterator():
            yield writer.writerow([
                c.order.reference,
                c.shop.name,
                c.shop.slug,
                c.shop.owner.username,
                c.shop.owner.email,
                c.created_at.strftime("%Y-%m-%d %H:%M"),
                c.sale_amount_xof,
                f"{c.rate}",
                c.commission_xof,
                c.merchant_amount_xof,
                "oui" if c.is_paid else "non",
                c.paid_at.strftime("%Y-%m-%d") if c.paid_at else "",
                c.payout_reference or "",
            ])

    response = StreamingHttpResponse(rows(), content_type="text/csv; charset=utf-8")
    fname = f"commissions_{filter_state}_{timezone.now().strftime('%Y%m%d_%H%M')}.csv"
    response["Content-Disposition"] = f'attachment; filename="{fname}"'
    return response


@platform_admin_required
def admin_monthly(request):
    """Récap mensuel (12 derniers mois) + drill-down par boutique pour le mois en cours."""
    months = get_monthly_summary(months=12)

    now = timezone.now()
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    shops_month = (
        Shop.objects.filter(is_approved=True)
        .annotate(
            gmv_month=Sum(
                "orders__total_xof",
                filter=Q(
                    orders__created_at__gte=start,
                    orders__payment_status=Order.PaymentStatus.PAID,
                ),
            ),
            commission_month=Sum(
                "orders__commission_xof",
                filter=Q(
                    orders__created_at__gte=start,
                    orders__payment_status=Order.PaymentStatus.PAID,
                ),
            ),
            orders_count=Count(
                "orders",
                filter=Q(
                    orders__created_at__gte=start,
                    orders__payment_status=Order.PaymentStatus.PAID,
                ),
            ),
        )
        .filter(orders_count__gt=0)
        .order_by("-gmv_month")
    )

    return render(request, "admin_panel/monthly.html", {
        "months": months,
        "shops_month": shops_month,
        "current_month_label": now.strftime("%B %Y"),
    })


# ============ NOTIFICATIONS (logs SMS / Email) ============

@platform_admin_required
def admin_notifications(request):
    channel = (request.GET.get("channel") or "").strip()
    status = (request.GET.get("status") or "").strip()
    q = (request.GET.get("q") or "").strip()

    qs = NotificationLog.objects.order_by("-created_at")
    if channel in {NotificationLog.Channel.SMS, NotificationLog.Channel.EMAIL}:
        qs = qs.filter(channel=channel)
    if status in {
        NotificationLog.Status.PENDING,
        NotificationLog.Status.SENT,
        NotificationLog.Status.FAILED,
    }:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(Q(recipient__icontains=q) | Q(body__icontains=q))

    counts = NotificationLog.objects.aggregate(
        total=Count("id"),
        sent=Count("id", filter=Q(status=NotificationLog.Status.SENT)),
        failed=Count("id", filter=Q(status=NotificationLog.Status.FAILED)),
        pending=Count("id", filter=Q(status=NotificationLog.Status.PENDING)),
    )

    return render(request, "admin_panel/notifications_list.html", {
        "notifications": qs[:200],
        "channel": channel, "status": status, "q": q,
        "counts": counts,
    })


# ============ WEBHOOKS (événements providers) ============

@platform_admin_required
def admin_webhooks(request):
    provider = (request.GET.get("provider") or "").strip()
    state = (request.GET.get("state") or "").strip()

    qs = WebhookEvent.objects.order_by("-received_at")
    if provider:
        qs = qs.filter(provider=provider)
    if state == "processed":
        qs = qs.filter(processed=True)
    elif state == "unprocessed":
        qs = qs.filter(processed=False)
    elif state == "invalid_signature":
        qs = qs.filter(signature_valid=False)
    elif state == "errored":
        qs = qs.exclude(error="")

    agg = WebhookEvent.objects.aggregate(
        total=Count("id"),
        ok=Count("id", filter=Q(processed=True)),
        waiting=Count("id", filter=Q(processed=False)),
        bad_sig=Count("id", filter=Q(signature_valid=False)),
    )
    counts = {
        "total": agg["total"],
        "processed": agg["ok"],
        "unprocessed": agg["waiting"],
        "invalid": agg["bad_sig"],
    }
    providers = (
        WebhookEvent.objects.values_list("provider", flat=True).distinct().order_by("provider")
    )

    return render(request, "admin_panel/webhooks_list.html", {
        "webhooks": qs[:200],
        "provider": provider, "state": state,
        "counts": counts,
        "providers": providers,
    })


@platform_admin_required
def admin_webhook_detail(request, pk):
    event = get_object_or_404(WebhookEvent, pk=pk)
    return render(request, "admin_panel/webhook_detail.html", {"event": event})


# ============ LIVREURS (cross-boutique) ============

@platform_admin_required
def admin_couriers(request):
    q = (request.GET.get("q") or "").strip()
    shop_slug = (request.GET.get("shop") or "").strip()
    active = (request.GET.get("active") or "").strip()

    qs = Courier.objects.select_related("shop").annotate(
        deliveries_count=Count(
            "orders",
            filter=Q(orders__status=Order.Status.DELIVERED),
        ),
    ).order_by("shop__name", "name")

    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(phone__icontains=q))
    if shop_slug:
        qs = qs.filter(shop__slug=shop_slug)
    if active == "yes":
        qs = qs.filter(is_active=True)
    elif active == "no":
        qs = qs.filter(is_active=False)

    return render(request, "admin_panel/couriers_list.html", {
        "couriers": qs,
        "q": q, "shop_slug": shop_slug, "active": active,
        "shops": Shop.objects.filter(is_approved=True).order_by("name"),
    })


# ============ RÉGLAGES PLATEFORME ============

@platform_admin_required
def admin_settings(request):
    settings_obj = PlatformSettings.load()
    return render(request, "admin_panel/settings.html", {"settings": settings_obj})


@platform_admin_required
@require_POST
def admin_settings_update(request):
    s = PlatformSettings.load()

    raw_rate = (request.POST.get("default_commission_rate") or "").replace(",", ".").strip()
    try:
        rate = Decimal(raw_rate)
        if not (Decimal("0") <= rate <= Decimal("50")):
            raise InvalidOperation
        s.default_commission_rate = rate
    except (InvalidOperation, ValueError):
        messages.error(request, "Taux de commission par défaut invalide (0–50).")
        return redirect("admin_panel:settings")

    s.sms_enabled = request.POST.get("sms_enabled") == "on"
    s.email_enabled = request.POST.get("email_enabled") == "on"
    s.support_phone = (request.POST.get("support_phone") or "").strip()[:20]
    s.support_email = (request.POST.get("support_email") or "").strip()[:254]
    s.maintenance_message = (request.POST.get("maintenance_message") or "").strip()
    s.save()

    log_admin_action(
        actor=request.user,
        action=AdminAction.Action.SETTINGS_UPDATED,
        target=s,
        target_repr="Réglages plateforme",
        meta={
            "default_commission_rate": str(s.default_commission_rate),
            "sms_enabled": s.sms_enabled,
            "email_enabled": s.email_enabled,
        },
    )
    messages.success(request, "Réglages plateforme mis à jour.")
    return redirect("admin_panel:settings")


# ============ CATALOGUE (produits cross-boutique) ============

@platform_admin_required
def admin_products(request):
    q = (request.GET.get("q") or "").strip()
    shop_slug = (request.GET.get("shop") or "").strip()
    category_name = (request.GET.get("category") or "").strip()
    active = (request.GET.get("active") or "").strip()
    stock_state = (request.GET.get("stock") or "").strip()

    qs = (
        Product.objects
        .select_related("shop", "category")
        .order_by("-created_at")
    )
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(slug__icontains=q))
    if shop_slug:
        qs = qs.filter(shop__slug=shop_slug)
    if category_name:
        qs = qs.filter(category__name__iexact=category_name)
    if active == "yes":
        qs = qs.filter(is_active=True)
    elif active == "no":
        qs = qs.filter(is_active=False)
    if stock_state == "out":
        qs = qs.filter(stock=0, track_stock=True)
    elif stock_state == "low":
        qs = qs.filter(stock__gt=0, stock__lte=5, track_stock=True)

    counts = Product.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        out_of_stock=Count("id", filter=Q(stock=0, track_stock=True)),
    )

    return render(request, "admin_panel/products_list.html", {
        "products": qs[:200],
        "q": q, "shop_slug": shop_slug, "category_name": category_name,
        "active": active, "stock_state": stock_state,
        "counts": counts,
        "shops": Shop.objects.filter(is_approved=True).order_by("name"),
        "categories": (
            Category.objects.values_list("name", flat=True).distinct().order_by("name")
        ),
    })


@platform_admin_required
@require_POST
def admin_product_toggle_active(request, pk):
    product = get_object_or_404(Product.objects.select_related("shop"), pk=pk)
    product.is_active = not product.is_active
    product.save(update_fields=["is_active", "updated_at"])
    log_admin_action(
        actor=request.user,
        action=AdminAction.Action.PRODUCT_TOGGLED,
        target=product,
        target_repr=f"{product.name} ({product.shop.name})",
        meta={"is_active": product.is_active},
    )
    state = "activé" if product.is_active else "masqué"
    messages.success(request, f"Produit « {product.name} » {state}.")
    return redirect(request.META.get("HTTP_REFERER") or "admin_panel:products")


# ============ CATÉGORIES (agrégées cross-boutique) ============

@platform_admin_required
def admin_categories(request):
    """Vue agrégée des catégories par nom (cross-boutique).

    On regroupe par nom (insensible à la casse) pour compenser le fait que
    chaque boutique a ses propres catégories. Utile pour voir ce qui se vend
    le mieux au niveau plateforme.
    """
    # Agrégation par nom de catégorie (lowercased)
    cat_groups = (
        Category.objects
        .annotate(lname=Lower("name"))
        .values("lname")
        .annotate(
            display_name=Max("name"),
            shops_count=Count("shop", distinct=True),
            products_count=Count("products"),
            active_products=Count("products", filter=Q(products__is_active=True)),
        )
        .order_by("-products_count")
    )

    # Revenus + unités vendues par catégorie (via OrderItem → Product → Category)
    from django.db.models import F, IntegerField
    from django.db.models.expressions import ExpressionWrapper
    from orders.models import OrderItem
    revenue_by_cat = (
        OrderItem.objects
        .filter(order__payment_status=Order.PaymentStatus.PAID)
        .annotate(lname=Lower("product__category__name"))
        .exclude(lname="")
        .annotate(line=ExpressionWrapper(F("unit_price_xof") * F("quantity"), output_field=IntegerField()))
        .values("lname")
        .annotate(
            units=Sum("quantity"),
            revenue=Sum("line"),
        )
    )
    revenue_map = {r["lname"]: r for r in revenue_by_cat if r["lname"]}

    rows = []
    for g in cat_groups:
        lname = g["lname"]
        rev = revenue_map.get(lname, {})
        rows.append({
            "name": g["display_name"],
            "shops_count": g["shops_count"],
            "products_count": g["products_count"],
            "active_products": g["active_products"],
            "units_sold": rev.get("units") or 0,
            "revenue": rev.get("revenue") or 0,
        })

    rows.sort(key=lambda r: r["revenue"], reverse=True)

    return render(request, "admin_panel/categories_list.html", {
        "categories": rows,
    })


# ============ JOURNAL D'AUDIT ============

@platform_admin_required
def admin_audit(request):
    action = (request.GET.get("action") or "").strip()
    actor_id = (request.GET.get("actor") or "").strip()
    q = (request.GET.get("q") or "").strip()

    qs = AdminAction.objects.select_related("actor").order_by("-created_at")
    if action:
        qs = qs.filter(action=action)
    if actor_id.isdigit():
        qs = qs.filter(actor_id=int(actor_id))
    if q:
        qs = qs.filter(Q(target_repr__icontains=q) | Q(target_id__icontains=q))

    from django.contrib.auth import get_user_model
    User = get_user_model()
    actors = (
        User.objects.filter(admin_actions__isnull=False)
        .distinct().order_by("username")
    )

    return render(request, "admin_panel/audit_list.html", {
        "actions": qs[:300],
        "q": q, "action": action, "actor_id": actor_id,
        "action_choices": AdminAction.Action.choices,
        "actors": actors,
    })


# ============ UTILISATEURS (commerçants + admins) ============

@platform_admin_required
def admin_users(request):
    from datetime import timedelta
    from django.contrib.auth import get_user_model

    User = get_user_model()
    role = (request.GET.get("role") or "merchant").strip()
    q = (request.GET.get("q") or "").strip()
    state = (request.GET.get("state") or "").strip()

    now = timezone.now()
    zombie_threshold = now - timedelta(days=30)

    qs = User.objects.filter(role__in=[User.Role.MERCHANT, User.Role.ADMIN])
    if role == "merchant":
        qs = qs.filter(role=User.Role.MERCHANT)
    elif role == "admin":
        qs = qs.filter(Q(role=User.Role.ADMIN) | Q(is_superuser=True))

    if q:
        qs = qs.filter(
            Q(username__icontains=q)
            | Q(email__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(phone__icontains=q)
        )
    if state == "active":
        qs = qs.filter(is_active=True)
    elif state == "blocked":
        qs = qs.filter(is_active=False)
    elif state == "zombie":
        qs = qs.filter(
            Q(last_login__lt=zombie_threshold) | Q(last_login__isnull=True),
            is_active=True,
            role=User.Role.MERCHANT,
        )

    qs = qs.annotate(
        orders_30d=Count(
            "shop__orders",
            filter=Q(shop__orders__created_at__gte=zombie_threshold),
        ),
    ).select_related("shop").order_by("-last_login", "-created_at")

    # KPIs (globaux, pas filtrés)
    merchants_qs = User.objects.filter(role=User.Role.MERCHANT)
    counts = {
        "merchants_total": merchants_qs.count(),
        "merchants_active": merchants_qs.filter(is_active=True).count(),
        "merchants_blocked": merchants_qs.filter(is_active=False).count(),
        "merchants_zombie": merchants_qs.filter(
            Q(last_login__lt=zombie_threshold) | Q(last_login__isnull=True),
            is_active=True,
        ).count(),
        "admins_total": User.objects.filter(
            Q(role=User.Role.ADMIN) | Q(is_superuser=True)
        ).distinct().count(),
    }

    return render(request, "admin_panel/users_list.html", {
        "users": qs[:200],
        "role": role, "q": q, "state": state,
        "counts": counts,
        "zombie_threshold": zombie_threshold,
    })


@platform_admin_required
@require_POST
def admin_user_toggle_active(request, pk):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    user = get_object_or_404(User, pk=pk)

    # Garde-fou : on ne bloque pas son propre compte
    if user.pk == request.user.pk:
        messages.error(request, "Impossible de bloquer ton propre compte.")
        return redirect("admin_panel:users")

    # Garde-fou : un admin ne peut pas bloquer un superuser
    if user.is_superuser and not request.user.is_superuser:
        messages.error(request, "Seul un superuser peut bloquer un autre superuser.")
        return redirect("admin_panel:users")

    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])
    log_admin_action(
        actor=request.user,
        action=AdminAction.Action.USER_TOGGLED,
        target=user,
        target_repr=f"{user.username} ({user.email})",
        meta={"is_active": user.is_active, "role": user.role},
    )
    state = "débloqué" if user.is_active else "bloqué"
    messages.success(request, f"Utilisateur « {user.username} » {state}.")
    return redirect(request.META.get("HTTP_REFERER") or "admin_panel:users")


@platform_admin_required
@require_POST
def admin_user_send_reengage(request, pk):
    """Envoie un SMS de relance à un commerçant zombie."""
    from django.contrib.auth import get_user_model
    from notifications.services.sms import send_sms

    User = get_user_model()
    user = get_object_or_404(User, pk=pk)

    if user.role != User.Role.MERCHANT:
        messages.error(request, "La relance ne s'adresse qu'aux commerçants.")
        return redirect("admin_panel:users")

    if not user.phone:
        messages.error(request, f"{user.username} n'a pas de téléphone renseigné.")
        return redirect("admin_panel:users")

    shop_name = user.shop.name if hasattr(user, "shop") and user.shop else "ta boutique"
    first_name = user.first_name or user.username
    message = (
        f"Bonjour {first_name}, on remarque que tu ne t'es pas connecté à "
        f"Jayma ({shop_name}) depuis un moment. Tout va bien ? "
        f"Besoin d'aide pour relancer les ventes ? Réponds à ce SMS ou "
        f"appelle-nous. — L'équipe Jayma"
    )

    log = send_sms(user.phone, message)
    log_admin_action(
        actor=request.user,
        action=AdminAction.Action.MERCHANT_REENGAGE_SENT,
        target=user,
        target_repr=f"{user.username} ({user.phone})",
        meta={"notification_id": log.pk, "status": log.status},
    )

    if log.status == "failed":
        messages.warning(request, f"SMS en échec pour {user.phone} : {log.error[:120]}")
    else:
        messages.success(request, f"SMS de relance envoyé à {user.phone}.")
    return redirect(request.META.get("HTTP_REFERER") or "admin_panel:users")
