"""Vues shops — boutique publique + paramètres dashboard."""
from django.contrib import messages
from django.core.cache import cache
from django.db import models
from django.db.models import Count
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.decorators import merchant_required

from .forms import ShopSettingsForm

# ============ PUBLIC ============

def shop_public_home(request):
    if not request.shop:
        raise Http404("Aucune boutique détectée sur ce sous-domaine.")

    shop = request.shop
    featured = shop.products.filter(is_active=True, is_featured=True).prefetch_related("images")[:8]
    latest = shop.products.filter(is_active=True).prefetch_related("images")[:8]
    categories = shop.categories.filter(is_active=True).annotate(products_count=Count("products"))

    # Bannière promo : premier coupon actif + dans les dates + quota non atteint
    now = timezone.now()
    promo_banner = (
        shop.coupons
        .filter(is_active=True, valid_from__lte=now)
        .filter(models.Q(valid_until__isnull=True) | models.Q(valid_until__gte=now))
        .order_by("valid_from")
        .first()
    )
    if promo_banner and promo_banner.max_uses is not None and promo_banner.uses_count >= promo_banner.max_uses:
        promo_banner = None

    return render(request, "shops/public_home.html", {
        "shop": shop, "featured": featured, "latest": latest, "categories": categories,
        "promo_banner": promo_banner,
    })


# ============ DASHBOARD ============

@merchant_required
def shop_settings(request):
    shop = request.merchant_shop
    if request.method == "POST":
        form = ShopSettingsForm(request.POST, request.FILES, instance=shop)
        if form.is_valid():
            form.save()
            cache.delete(f"shop:slug:{shop.slug}")
            messages.success(request, "Paramètres de ta boutique enregistrés.")
            return redirect("shops_dashboard:settings")
    else:
        form = ShopSettingsForm(instance=shop)
    return render(request, "dashboard/shop/settings.html", {
        "shop": shop, "form": form,
    })
