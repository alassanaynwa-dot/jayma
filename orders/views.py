"""Vues orders — checkout public + gestion commandes commerçant."""
from django.contrib import messages
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import merchant_required
from cart.services.cart import Cart

from .forms import CheckoutForm
from .models import Order
from .services.checkout import CheckoutError, create_order_from_cart
from .services.workflow import TransitionError, transition_order


# ======================== PUBLIC ========================

def checkout(request):
    if not request.shop:
        raise Http404()
    cart = Cart(request)
    if len(cart) == 0:
        messages.warning(request, "Ton panier est vide.")
        return redirect("cart:view")

    from cart.services.abandonment import snapshot_cart

    # Pré-remplir si client connecté
    initial = {}
    if request.user.is_authenticated and getattr(request.user, "is_client", False):
        user = request.user
        default_addr = user.addresses.filter(is_default=True).first() or user.addresses.first()
        initial.update({
            "client_name": user.get_full_name() or user.first_name,
            "client_phone": user.phone,
            "client_email": user.email,
        })
        if default_addr:
            initial.update({
                "client_address": default_addr.address,
                "client_city": default_addr.city,
            })

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            try:
                order = create_order_from_cart(request, request.shop, form.cleaned_data)
            except CheckoutError as exc:
                messages.error(request, str(exc))
                return redirect("cart:view")
            return redirect("orders_public:confirmation", reference=order.reference)
        # Form invalide MAIS on a un phone valide → snapshot panier abandonné
        phone = request.POST.get("client_phone", "")
        name = request.POST.get("client_name", "")
        if phone:
            snapshot_cart(request, request.shop, phone, name)
    else:
        form = CheckoutForm(initial=initial)
        # GET : si on a déjà le phone (client connecté), on snapshot
        if initial.get("client_phone"):
            snapshot_cart(
                request, request.shop,
                initial["client_phone"], initial.get("client_name", ""),
            )

    from coupons.services.application import compute_cart_discount
    coupon_result = compute_cart_discount(request, request.shop, cart.total_xof)
    total_estimate = max(cart.total_xof - coupon_result.discount_xof, 0)

    return render(request, "orders/checkout.html", {
        "shop": request.shop, "cart": cart, "form": form,
        "active_coupon": coupon_result.coupon,
        "active_discount": coupon_result.discount_xof,
        "total_estimate": total_estimate,
    })


def order_confirmation(request, reference):
    if not request.shop:
        raise Http404()
    order = get_object_or_404(Order, reference=reference, shop=request.shop)
    return render(request, "orders/confirmation.html", {"shop": request.shop, "order": order})


def order_tracking(request):
    """
    Page publique de suivi de commande — accessible sans compte.
    Le client tape sa référence + son téléphone, on affiche la timeline.
    Sécurité : on exige le téléphone correspondant pour éviter l'énumération.
    """
    if not request.shop:
        raise Http404()

    order = None
    error = None
    reference = (request.GET.get("ref") or "").strip().upper()
    phone = (request.GET.get("phone") or "").replace(" ", "").strip()

    if reference and phone:
        found = Order.objects.filter(
            shop=request.shop, reference__iexact=reference,
        ).first()
        if found is None or found.client_phone.replace(" ", "") != phone:
            error = "Aucune commande trouvée avec ces informations."
        else:
            order = found

    timeline = _build_timeline(order) if order else []

    return render(request, "orders/tracking.html", {
        "shop": request.shop,
        "order": order,
        "reference": reference,
        "phone": phone,
        "error": error,
        "timeline": timeline,
    })


def _build_timeline(order):
    """Retourne les 4 étapes de la commande avec leur état (done / current / pending)."""
    steps = [
        ("pending",   "Commande reçue",      "📝", order.created_at),
        ("confirmed", "Commande confirmée",  "✓",  None),
        ("shipped",   "En livraison",        "🚚", None),
        ("delivered", "Livrée",              "🎉", order.delivered_at),
    ]
    if order.status == Order.Status.CANCELLED:
        return [{
            "key": "cancelled", "label": "Commande annulée",
            "icon": "✕", "state": "cancelled", "at": order.updated_at,
        }]

    status_order = ["pending", "confirmed", "shipped", "delivered"]
    try:
        current_index = status_order.index(order.status)
    except ValueError:
        current_index = 0

    result = []
    for i, (key, label, icon, at) in enumerate(steps):
        if i < current_index:
            state = "done"
        elif i == current_index:
            state = "current"
        else:
            state = "pending"
        result.append({"key": key, "label": label, "icon": icon, "state": state, "at": at})
    return result


def rate_delivery(request, reference):
    """Le client note la livraison (depuis page confirmation ou lien SMS)."""
    if not request.shop:
        raise Http404()
    order = get_object_or_404(Order, reference=reference, shop=request.shop)

    if order.status != Order.Status.DELIVERED or not order.courier:
        messages.error(request, "Cette commande ne peut pas encore être notée.")
        return redirect("orders_public:confirmation", reference=order.reference)

    if order.delivery_rating:
        messages.info(request, "Tu as déjà noté cette livraison, merci !")
        return redirect("orders_public:confirmation", reference=order.reference)

    if request.method == "POST":
        from django.utils import timezone
        try:
            rating = int(request.POST.get("rating", 0))
        except (TypeError, ValueError):
            rating = 0
        if not (1 <= rating <= 5):
            messages.error(request, "Choisis une note entre 1 et 5 étoiles.")
            return redirect("orders_public:rate_delivery", reference=order.reference)

        order.delivery_rating = rating
        order.delivery_rating_comment = (request.POST.get("comment") or "")[:500]
        order.delivery_rated_at = timezone.now()
        order.save(update_fields=[
            "delivery_rating", "delivery_rating_comment", "delivery_rated_at", "updated_at",
        ])
        messages.success(request, "Merci pour ta note !")
        return redirect("orders_public:confirmation", reference=order.reference)

    return render(request, "orders/rate_delivery.html", {
        "shop": request.shop, "order": order,
    })


# ======================== DASHBOARD COMMERÇANT ========================

@merchant_required
def orders_list(request):
    shop = request.merchant_shop
    orders = shop.orders.prefetch_related("items")

    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    if q:
        orders = orders.filter(
            Q(reference__icontains=q)
            | Q(client_name__icontains=q)
            | Q(client_phone__icontains=q)
        )
    if status:
        orders = orders.filter(status=status)

    stats = {
        "pending": shop.orders.filter(status=Order.Status.PENDING).count(),
        "confirmed": shop.orders.filter(status=Order.Status.CONFIRMED).count(),
        "shipped": shop.orders.filter(status=Order.Status.SHIPPED).count(),
    }

    return render(request, "dashboard/orders/list.html", {
        "shop": shop, "orders": orders, "q": q, "status": status,
        "stats": stats, "statuses": Order.Status.choices,
    })


@merchant_required
def order_detail(request, reference):
    shop = request.merchant_shop
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product", "payments"),
        reference=reference, shop=shop,
    )
    return render(request, "dashboard/orders/detail.html", {
        "shop": shop, "order": order,
    })


@merchant_required
@require_POST
def order_update_status(request, reference):
    shop = request.merchant_shop
    order = get_object_or_404(Order, reference=reference, shop=shop)
    new_status = request.POST.get("status")
    notify = request.POST.get("notify", "1") == "1"
    try:
        transition_order(order, new_status, notify=notify)
    except TransitionError as exc:
        messages.error(request, str(exc))
        return redirect("orders_dashboard:detail", reference=order.reference)

    msg = f"Commande {order.reference} → {order.get_status_display()}"
    if notify:
        msg += " (SMS envoyé au client)"
    messages.success(request, msg)
    return redirect("orders_dashboard:detail", reference=order.reference)


@merchant_required
@require_POST
def order_update_tracking(request, reference):
    shop = request.merchant_shop
    order = get_object_or_404(Order, reference=reference, shop=shop)
    order.tracking_number = request.POST.get("tracking_number", "").strip()[:100]
    order.notes = request.POST.get("notes", "").strip()
    order.save(update_fields=["tracking_number", "notes", "updated_at"])
    messages.success(request, "Informations mises à jour.")
    return redirect("orders_dashboard:detail", reference=order.reference)
