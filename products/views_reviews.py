"""Vues d'avis produits côté client."""
from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from orders.models import Order, OrderItem

from .models import Product, ProductReview


def reviews_for_order(request, reference):
    """
    Page où un client note tous les produits d'une commande livrée.
    Accessible via un lien SMS envoyé après livraison.
    Sécurité : vérifier phone pour éviter l'énumération.
    """
    if not request.shop:
        raise Http404()

    order = get_object_or_404(Order, reference=reference, shop=request.shop)

    if order.status != Order.Status.DELIVERED:
        messages.error(request, "Tu pourras noter tes produits une fois la commande livrée.")
        return redirect("orders_public:confirmation", reference=order.reference)

    # Vérification via query string ?phone=...
    phone = (request.GET.get("phone") or "").replace(" ", "").strip()
    if phone and phone != order.client_phone.replace(" ", ""):
        raise Http404()

    # Liste des produits avec indication "déjà noté" pour chacun
    items = []
    for item in order.items.filter(product__isnull=False).select_related("product"):
        existing = ProductReview.objects.filter(
            product=item.product, client_phone=order.client_phone,
        ).first()
        items.append({"order_item": item, "product": item.product, "review": existing})

    return render(request, "products/reviews_for_order.html", {
        "shop": request.shop, "order": order, "items": items,
    })


@require_POST
def submit_review(request, reference, product_pk):
    """Soumet un avis pour un produit d'une commande livrée."""
    if not request.shop:
        raise Http404()

    order = get_object_or_404(Order, reference=reference, shop=request.shop)
    product = get_object_or_404(Product, pk=product_pk, shop=request.shop)

    # Validation : commande livrée + produit présent dans la commande
    if order.status != Order.Status.DELIVERED:
        raise Http404()
    if not OrderItem.objects.filter(order=order, product=product).exists():
        raise Http404()

    try:
        rating = int(request.POST.get("rating", 0))
    except (TypeError, ValueError):
        rating = 0
    if not (1 <= rating <= 5):
        messages.error(request, "Choisis une note entre 1 et 5 étoiles.")
        return redirect("products_public:reviews_for_order", reference=order.reference)

    comment = (request.POST.get("comment") or "").strip()[:1000]
    title = (request.POST.get("title") or "").strip()[:120]

    review, created = ProductReview.objects.update_or_create(
        product=product,
        client_phone=order.client_phone,
        defaults={
            "order": order,
            "client_name": order.client_name,
            "rating": rating,
            "comment": comment,
            "title": title,
            "is_approved": True,
        },
    )
    messages.success(
        request,
        f"Merci pour ton avis sur « {product.name} » !" if created else "Ton avis a été mis à jour."
    )
    return redirect("products_public:reviews_for_order", reference=order.reference)
