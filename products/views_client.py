"""Vues client (favoris + alertes stock) — côté boutique publique."""
from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from accounts.views_client import client_required

from .models import Favorite, Product, StockAlert

# ============ FAVORIS ============

@client_required
@require_POST
def toggle_favorite(request, product_id):
    """Ajoute/retire un produit des favoris. HTMX ou classique."""
    if not request.shop:
        raise Http404()
    product = get_object_or_404(Product, pk=product_id, shop=request.shop, is_active=True)

    fav, created = Favorite.objects.get_or_create(user=request.user, product=product)
    if not created:
        fav.delete()
        is_fav = False
    else:
        is_fav = True

    if request.headers.get("HX-Request"):
        return render(request, "products/_favorite_btn.html", {
            "product": product, "is_favorite": is_fav,
        })
    messages.success(request, "Ajouté aux favoris ✓" if is_fav else "Retiré des favoris")
    return redirect("products_public:detail", slug=product.slug)


@client_required
def favorites_list(request):
    """Liste des produits mis en favori par le client courant."""
    shop = request.shop
    # Ne montre que les favoris liés aux produits de cette boutique
    favs = (
        Favorite.objects
        .filter(user=request.user, product__shop=shop, product__is_active=True)
        .select_related("product", "product__category")
        .prefetch_related("product__images")
    )
    products = [f.product for f in favs]
    return render(request, "client/favorites.html", {
        "shop": shop, "products": products,
    })


# ============ ALERTE RETOUR EN STOCK ============

@ratelimit(key="ip", rate="10/m", method="POST", block=True)
@ratelimit(key="post:phone", rate="3/m", method="POST", block=True)
@require_POST
def register_stock_alert(request, product_id):
    """
    Inscrit un client à l'alerte retour en stock.
    Le phone peut venir du user connecté ou être saisi manuellement.
    """
    if not request.shop:
        raise Http404()
    product = get_object_or_404(Product, pk=product_id, shop=request.shop, is_active=True)

    # Récupérer le phone (user connecté OU saisie form)
    phone = ""
    if request.user.is_authenticated and getattr(request.user, "is_client", False):
        phone = request.user.phone
    phone = (request.POST.get("phone") or phone).replace(" ", "").strip()

    if not phone:
        if request.headers.get("HX-Request"):
            return render(request, "products/_stock_alert_btn.html", {
                "product": product, "error": "Numéro de téléphone requis.",
            })
        messages.error(request, "Numéro de téléphone requis.")
        return redirect("products_public:detail", slug=product.slug)

    from django.core.exceptions import ValidationError

    from accounts.models import phone_validator
    try:
        phone_validator(phone)
    except ValidationError:
        if request.headers.get("HX-Request"):
            return render(request, "products/_stock_alert_btn.html", {
                "product": product, "error": "Numéro sénégalais invalide.",
            })
        messages.error(request, "Numéro sénégalais invalide.")
        return redirect("products_public:detail", slug=product.slug)

    alert, created = StockAlert.objects.get_or_create(
        product=product, client_phone=phone,
        defaults={"notified_at": None},
    )

    if request.headers.get("HX-Request"):
        return render(request, "products/_stock_alert_btn.html", {
            "product": product, "registered": True, "just_created": created,
        })
    messages.success(
        request,
        "On te préviendra par SMS dès le retour en stock !"
        if created else "Tu es déjà inscrit pour ce produit."
    )
    return redirect("products_public:detail", slug=product.slug)
