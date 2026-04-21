"""Vues panier — toutes HTMX-compatibles."""
from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from products.models import Product

from .services.cart import Cart


def cart_view(request):
    """Page /panier/ — liste complète."""
    cart = Cart(request)
    return render(request, "cart/cart.html", {"cart": cart, "shop": request.shop})


@require_POST
def cart_add(request, product_id):
    """Ajoute un produit au panier (POST, HTMX ou classique)."""
    if not request.shop:
        raise Http404()
    product = get_object_or_404(Product, pk=product_id, shop=request.shop, is_active=True)
    try:
        quantity = max(1, int(request.POST.get("quantity", 1)))
    except ValueError:
        quantity = 1

    # Borne par le stock si tracké
    if product.track_stock:
        quantity = min(quantity, max(product.stock, 0))
        if quantity == 0:
            return HttpResponse("Stock épuisé", status=409)

    cart = Cart(request)
    cart.add(product, quantity=quantity)

    if request.headers.get("HX-Request"):
        # On renvoie juste le compteur refreshed (cible = #cart-counter)
        return render(request, "cart/_cart_counter.html", {"count": len(cart)})
    messages.success(request, f"{product.name} ajouté au panier.")
    return redirect("cart:view")


@require_POST
def cart_update(request, product_id):
    """Met à jour la quantité d'un item (input number HTMX)."""
    cart = Cart(request)
    try:
        quantity = max(0, int(request.POST.get("quantity", 1)))
    except ValueError:
        quantity = 1

    if quantity == 0:
        cart.remove(product_id)
    else:
        pid = str(product_id)
        if pid in cart.cart["items"]:
            cart.cart["items"][pid]["quantity"] = quantity
            cart._save()

    if request.headers.get("HX-Request"):
        # Renvoie le contenu panier entier pour refresh
        return render(request, "cart/_cart_body.html", {"cart": cart})
    return redirect("cart:view")


@require_POST
def cart_remove(request, product_id):
    cart = Cart(request)
    cart.remove(product_id)
    if request.headers.get("HX-Request"):
        return render(request, "cart/_cart_body.html", {"cart": cart})
    return redirect("cart:view")


@require_POST
def cart_clear(request):
    Cart(request).clear()
    return redirect("cart:view")
