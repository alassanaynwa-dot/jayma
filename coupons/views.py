"""Vues coupons — CRUD dashboard + apply/remove au checkout."""
from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import merchant_required
from cart.services.cart import Cart

from .forms import CouponForm
from .models import Coupon
from .services.application import (
    clear_session_coupon,
    set_session_coupon,
    try_apply_coupon,
)

# =============== DASHBOARD ===============

@merchant_required
def coupon_list(request):
    shop = request.merchant_shop
    # Stats de conversion par coupon (jointure CouponUsage → Order → total)
    from django.db.models import Count as CountAgg
    from django.db.models import Sum
    coupons = shop.coupons.all().annotate(
        revenue_generated=Sum("usages__order__total_xof"),
        total_discount=Sum("usages__discount_xof"),
        unique_customers=CountAgg("usages__client_phone", distinct=True),
    )
    return render(request, "dashboard/coupons/list.html", {
        "shop": shop, "coupons": coupons,
    })


@merchant_required
def coupon_create(request):
    shop = request.merchant_shop
    if request.method == "POST":
        form = CouponForm(request.POST, shop=shop)
        if form.is_valid():
            c = form.save()
            messages.success(request, f"Code « {c.code} » créé.")
            return redirect("coupons_dashboard:list")
    else:
        form = CouponForm(shop=shop)
    return render(request, "dashboard/coupons/form.html", {
        "shop": shop, "form": form, "coupon": None,
    })


@merchant_required
def coupon_edit(request, pk):
    shop = request.merchant_shop
    c = get_object_or_404(Coupon, pk=pk, shop=shop)
    if request.method == "POST":
        form = CouponForm(request.POST, instance=c, shop=shop)
        if form.is_valid():
            form.save()
            messages.success(request, "Code promo mis à jour.")
            return redirect("coupons_dashboard:list")
    else:
        form = CouponForm(instance=c, shop=shop)
    return render(request, "dashboard/coupons/form.html", {
        "shop": shop, "form": form, "coupon": c,
    })


@merchant_required
@require_POST
def coupon_delete(request, pk):
    shop = request.merchant_shop
    c = get_object_or_404(Coupon, pk=pk, shop=shop)
    code = c.code
    c.delete()
    messages.success(request, f"Code « {code} » supprimé.")
    return redirect("coupons_dashboard:list")


# =============== CHECKOUT PUBLIC ===============

@require_POST
def apply_coupon(request):
    """HTMX — applique un coupon au panier courant."""
    if not request.shop:
        raise Http404()
    cart = Cart(request)
    code = (request.POST.get("code") or "").strip()
    result = try_apply_coupon(request.shop, code, cart.total_xof)

    if result.coupon is None:
        return render(request, "coupons/_coupon_box.html", {
            "subtotal": cart.total_xof,
            "error": result.error,
            "entered_code": code,
        })
    set_session_coupon(request.session, result.coupon.code)
    return render(request, "coupons/_coupon_box.html", {
        "subtotal": cart.total_xof,
        "coupon": result.coupon,
        "discount": result.discount_xof,
    })


@require_POST
def remove_coupon(request):
    if not request.shop:
        raise Http404()
    clear_session_coupon(request.session)
    cart = Cart(request)
    return render(request, "coupons/_coupon_box.html", {"subtotal": cart.total_xof})
