"""Vues livreurs — dashboard commerçant + portail livreur public."""
from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import merchant_required
from orders.models import Order

from .forms import CourierForm, DeliveryZoneForm
from .models import Courier, DeliveryZone
from .services.invite import build_portal_url, send_portal_link
from .services.tokens import parse_courier_token
from .services.zones import compute_delivery_fee, suggest_courier_for_order

# ================= DASHBOARD =================

@merchant_required
def courier_list(request):
    shop = request.merchant_shop
    couriers = shop.couriers.all()
    active_deliveries = Order.objects.filter(
        shop=shop, status=Order.Status.SHIPPED
    ).select_related("courier").count()
    return render(request, "dashboard/delivery/list.html", {
        "shop": shop,
        "couriers": couriers,
        "active_deliveries": active_deliveries,
    })


@merchant_required
def courier_create(request):
    shop = request.merchant_shop
    if request.method == "POST":
        form = CourierForm(request.POST, shop=shop)
        if form.is_valid():
            c = form.save()
            messages.success(request, f"Livreur {c.name} ajouté.")
            return redirect("delivery_dashboard:detail", pk=c.pk)
    else:
        form = CourierForm(shop=shop)
    return render(request, "dashboard/delivery/form.html", {
        "shop": shop, "form": form, "courier": None,
    })


@merchant_required
def courier_edit(request, pk):
    shop = request.merchant_shop
    c = get_object_or_404(Courier, pk=pk, shop=shop)
    if request.method == "POST":
        form = CourierForm(request.POST, instance=c, shop=shop)
        if form.is_valid():
            form.save()
            messages.success(request, "Livreur mis à jour.")
            return redirect("delivery_dashboard:detail", pk=c.pk)
    else:
        form = CourierForm(instance=c, shop=shop)
    return render(request, "dashboard/delivery/form.html", {
        "shop": shop, "form": form, "courier": c,
    })


@merchant_required
def courier_detail(request, pk):
    shop = request.merchant_shop
    c = get_object_or_404(Courier, pk=pk, shop=shop)
    orders = (
        Order.objects
        .filter(shop=shop, courier=c)
        .prefetch_related("items")
        .order_by("-created_at")[:50]
    )
    in_progress = [o for o in orders if o.status == Order.Status.SHIPPED]
    done = [o for o in orders if o.status == Order.Status.DELIVERED]
    portal_url = build_portal_url(c)

    from .services.ratings import get_courier_rating_stats
    rating_stats = get_courier_rating_stats(c)
    recent_ratings = (
        Order.objects
        .filter(shop=shop, courier=c, delivery_rating__isnull=False)
        .exclude(delivery_rating_comment="")
        .order_by("-delivery_rated_at")[:5]
    )

    return render(request, "dashboard/delivery/detail.html", {
        "shop": shop,
        "courier": c,
        "orders": orders,
        "in_progress": in_progress,
        "done": done,
        "portal_url": portal_url,
        "rating_stats": rating_stats,
        "recent_ratings": recent_ratings,
    })


@merchant_required
@require_POST
def courier_delete(request, pk):
    shop = request.merchant_shop
    c = get_object_or_404(Courier, pk=pk, shop=shop)
    name = c.name
    # SET_NULL sur Order — on ne perd pas l'historique
    c.delete()
    messages.success(request, f"Livreur {name} supprimé.")
    return redirect("delivery_dashboard:list")


@merchant_required
@require_POST
def courier_send_portal_link(request, pk):
    shop = request.merchant_shop
    c = get_object_or_404(Courier, pk=pk, shop=shop)
    send_portal_link(c)
    messages.success(request, f"Lien portail envoyé à {c.name} au {c.phone}.")
    return redirect("delivery_dashboard:detail", pk=c.pk)


# ================= ZONES TARIFÉES =================

@merchant_required
def zone_list(request):
    shop = request.merchant_shop
    return render(request, "dashboard/delivery/zones_list.html", {
        "shop": shop, "zones": shop.delivery_zones.all(),
    })


@merchant_required
def zone_create(request):
    shop = request.merchant_shop
    if request.method == "POST":
        form = DeliveryZoneForm(request.POST, shop=shop)
        if form.is_valid():
            z = form.save()
            messages.success(request, f"Zone « {z.name} » créée ({z.fee_xof} XOF).")
            return redirect("delivery_dashboard:zone_list")
    else:
        form = DeliveryZoneForm(shop=shop)
    return render(request, "dashboard/delivery/zones_form.html", {
        "shop": shop, "form": form, "zone": None,
    })


@merchant_required
def zone_edit(request, pk):
    shop = request.merchant_shop
    zone = get_object_or_404(DeliveryZone, pk=pk, shop=shop)
    if request.method == "POST":
        form = DeliveryZoneForm(request.POST, instance=zone, shop=shop)
        if form.is_valid():
            form.save()
            messages.success(request, "Zone mise à jour.")
            return redirect("delivery_dashboard:zone_list")
    else:
        form = DeliveryZoneForm(instance=zone, shop=shop)
    return render(request, "dashboard/delivery/zones_form.html", {
        "shop": shop, "form": form, "zone": zone,
    })


@merchant_required
@require_POST
def zone_delete(request, pk):
    shop = request.merchant_shop
    zone = get_object_or_404(DeliveryZone, pk=pk, shop=shop)
    name = zone.name
    zone.delete()
    messages.success(request, f"Zone « {name} » supprimée.")
    return redirect("delivery_dashboard:zone_list")


# ================= FRAIS HTMX (checkout live) =================

def compute_fee_partial(request):
    """
    Endpoint HTMX appelé au checkout quand le client tape sa ville :
    retourne le tarif de livraison applicable.
    """
    from django.http import Http404
    if not request.shop:
        raise Http404()
    city = request.GET.get("city", "").strip()
    fee, zone = compute_delivery_fee(request.shop, city)
    return render(request, "orders/_delivery_fee.html", {
        "fee": fee, "zone": zone, "city": city,
    })


# ================= ASSIGNATION depuis Order =================

@merchant_required
@require_POST
def assign_courier(request, reference):
    shop = request.merchant_shop
    order = get_object_or_404(Order, reference=reference, shop=shop)
    courier_id = request.POST.get("courier_id") or ""

    if courier_id == "":
        order.courier = None
    elif courier_id == "auto":
        order.courier = suggest_courier_for_order(order)
        if order.courier is None:
            messages.warning(request, "Aucun livreur actif ne couvre cette zone.")
            return redirect("orders_dashboard:detail", reference=order.reference)
    else:
        courier = get_object_or_404(Courier, pk=courier_id, shop=shop)
        order.courier = courier
    order.save(update_fields=["courier", "updated_at"])

    if order.courier:
        messages.success(request, f"Commande assignée à {order.courier.name}.")
        # SMS au livreur avec lien portail direct
        try:
            from notifications.services.sms import send_sms
            portal = build_portal_url(order.courier)
            send_sms(
                order.courier.phone,
                f"Nouvelle course {shop.name} — {order.reference}. "
                f"Client {order.client_name}, {order.client_city}. Ouvre : {portal}"
            )
        except Exception:
            pass
    else:
        messages.info(request, "Assignation retirée.")

    return redirect("orders_dashboard:detail", reference=order.reference)


# ================= PORTAIL LIVREUR PUBLIC =================

def _resolve_courier(request, token: str) -> Courier:
    """Vérifie le token et retourne le Courier, ou 404."""
    courier_id = parse_courier_token(token)
    if not courier_id:
        raise Http404("Lien invalide ou expiré.")
    courier = get_object_or_404(Courier, pk=courier_id, shop=request.shop, is_active=True)
    return courier


def portal_home(request, token):
    """Vue d'un livreur — ses courses en cours + historique."""
    if not request.shop:
        raise Http404()
    courier = _resolve_courier(request, token)

    in_progress = (
        Order.objects.filter(shop=request.shop, courier=courier, status=Order.Status.SHIPPED)
        .order_by("-created_at")
    )
    recent_done = (
        Order.objects.filter(shop=request.shop, courier=courier, status=Order.Status.DELIVERED)
        .order_by("-delivered_at")[:10]
    )
    return render(request, "delivery/portal.html", {
        "shop": request.shop,
        "courier": courier,
        "token": token,
        "in_progress": in_progress,
        "recent_done": recent_done,
    })


def portal_order_detail(request, token, reference):
    if not request.shop:
        raise Http404()
    courier = _resolve_courier(request, token)
    order = get_object_or_404(Order, reference=reference, shop=request.shop, courier=courier)
    return render(request, "delivery/portal_order.html", {
        "shop": request.shop, "courier": courier, "token": token, "order": order,
    })


@require_POST
def portal_mark_delivered(request, token, reference):
    """Le livreur valide la livraison — sécurisé par token."""
    if not request.shop:
        raise Http404()
    courier = _resolve_courier(request, token)
    order = get_object_or_404(Order, reference=reference, shop=request.shop, courier=courier)
    if order.status != Order.Status.SHIPPED:
        messages.error(request, "Cette course n'est pas en cours de livraison.")
        return redirect("delivery_portal:order", token=token, reference=reference)

    from orders.services.workflow import transition_order
    transition_order(order, Order.Status.DELIVERED, notify=True)
    messages.success(request, f"Livraison de {order.reference} confirmée. Merci !")
    return redirect("delivery_portal:home", token=token)
