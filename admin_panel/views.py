"""Vues admin.jayma.sn — dashboard owner de la plateforme."""
from django.contrib import messages
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from commissions.models import Commission
from core.tasks import send_merchant_welcome
from orders.models import Order
from shops.models import Shop, ShopRequest
from shops.services.approval import ApprovalError, approve_shop_request

from .decorators import platform_admin_required
from .services.stats import get_platform_stats


@platform_admin_required
def admin_home(request):
    return render(request, "admin_panel/home.html", {"stats": get_platform_stats()})


@platform_admin_required
def admin_requests(request):
    requests_qs = ShopRequest.objects.select_related("reviewed_by").order_by("-created_at")
    status = request.GET.get("status", "pending")
    if status:
        requests_qs = requests_qs.filter(status=status)
    return render(request, "admin_panel/requests.html", {
        "shop_requests": requests_qs,
        "status": status,
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
    messages.info(request, "Demande rejetée.")
    return redirect("admin_panel:requests")


@platform_admin_required
def admin_shops(request):
    shops = (
        Shop.objects.select_related("owner")
        .annotate(
            orders_count=Count("orders"),
            revenue=Sum("orders__total_xof", filter=None),
        )
        .order_by("-created_at")
    )
    return render(request, "admin_panel/shops.html", {"shops": shops})


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
        "commissions": qs,
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
    messages.success(request, f"Reversement pour {c.shop.name} marqué comme payé.")
    return redirect("admin_panel:commissions")
