"""Vues dashboard clients."""
from django.http import Http404
from django.shortcuts import render

from accounts.decorators import merchant_required

from .services.clients import get_client_orders, list_clients


@merchant_required
def clients_list(request):
    shop = request.merchant_shop
    q = request.GET.get("q", "").strip()
    clients = list_clients(shop, q=q)
    total_spent = sum(c.total_spent for c in clients)
    return render(request, "dashboard/clients/list.html", {
        "shop": shop,
        "clients": clients,
        "q": q,
        "total_clients": len(clients),
        "total_spent": total_spent,
    })


@merchant_required
def client_detail(request, phone):
    shop = request.merchant_shop
    orders = list(get_client_orders(shop, phone))
    if not orders:
        raise Http404("Client introuvable.")

    first = orders[-1]
    last = orders[0]
    total_spent = sum(o.total_xof for o in orders)
    paid_count = sum(1 for o in orders if o.payment_status == "paid")

    return render(request, "dashboard/clients/detail.html", {
        "shop": shop,
        "phone": phone,
        "orders": orders,
        "client_name": last.client_name,
        "client_email": last.client_email,
        "client_city": last.client_city,
        "client_address": last.client_address,
        "total_spent": total_spent,
        "orders_count": len(orders),
        "paid_count": paid_count,
        "first_order_at": first.created_at,
        "last_order_at": last.created_at,
    })
