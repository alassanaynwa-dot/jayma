"""Vues accounts — login/logout, dashboard redirect."""
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.shortcuts import redirect, render
from django_ratelimit.decorators import ratelimit

from .decorators import merchant_required
from .forms import LoginForm

# ============ URLs des tenants (pour suggestions de redirection) ============

def _tenant_url(request, sub: str) -> str:
    """Retourne //<sub>.{root}:{port}/comptes/login/ absolu."""
    host = request.get_host()
    port = ":" + host.split(":", 1)[1] if ":" in host else ""
    root = settings.JAYMA_ROOT_DOMAIN
    return f"//{sub}.{root}{port}/comptes/login/"


# ============ Vues ============

@ratelimit(key="ip", rate="10/m", method="POST", block=True)
@ratelimit(key="post:username", rate="5/m", method="POST", block=True)
def login_view(request):
    """
    Page de connexion — ses 3 incarnations :
      - jappesi.sn/comptes/login/           : login générique (tenant=public)
      - dashboard.jappesi.sn/comptes/login/ : pour les commerçants
      - admin.jappesi.sn/comptes/login/     : pour l'équipe Jappesi

    Si on se connecte sur le mauvais tenant (ex : commerçant sur admin),
    on bloque avec un message ET un bouton vers le bon login — ça évite
    les sessions perdues entre sous-domaines (cookies isolés par scope).
    """
    tenant = getattr(request, "tenant_type", "public")

    if request.user.is_authenticated:
        return redirect(_redirect_after_login(request, request.user))

    wrong_tenant_redirect = None  # URL du bon login si erreur

    if request.method == "POST":
        form = LoginForm(request.POST, request=request)
        if form.is_valid():
            user = form.user

            # Validation tenant <-> rôle (uniquement pour dashboard/admin)
            if tenant == "admin" and not user.is_platform_admin:
                form.add_error(None, "Cet espace est réservé à l'équipe Jappesi.")
                wrong_tenant_redirect = _tenant_url(request, "dashboard")
            elif tenant == "dashboard" and not user.is_merchant:
                form.add_error(None, "Cet espace est réservé aux commerçants.")
                wrong_tenant_redirect = _tenant_url(request, "admin")
            else:
                login(request, user)
                messages.success(request, f"Bienvenue {user.first_name or user.username} !")
                return redirect(_redirect_after_login(request, user))
    else:
        form = LoginForm(request=request)

    host = request.get_host()
    port = ":" + host.split(":", 1)[1] if ":" in host else ""
    public_url = f"//{settings.JAYMA_ROOT_DOMAIN}{port}"

    return render(request, "accounts/login.html", {
        "form": form,
        "tenant": tenant,
        "wrong_tenant_redirect": wrong_tenant_redirect,
        "dashboard_login_url": _tenant_url(request, "dashboard"),
        "admin_login_url": _tenant_url(request, "admin"),
        "public_url": public_url,
    })


def logout_view(request):
    logout(request)
    messages.info(request, "Tu es déconnecté(e).")
    return redirect("accounts:login")


def _redirect_after_login(request, user) -> str:
    """URL absolue du bon tenant selon le rôle, quelle que soit l'URL de login."""
    host = request.get_host()
    port = ":" + host.split(":", 1)[1] if ":" in host else ""
    root = settings.JAYMA_ROOT_DOMAIN

    if user.is_platform_admin:
        return f"//admin.{root}{port}/"
    if user.is_merchant:
        return f"//dashboard.{root}{port}/"
    return "/"


@merchant_required
def dashboard_home(request):
    """Accueil du dashboard commerçant (stats, actions rapides)."""
    from products.services.stats import get_dashboard_stats
    stats = get_dashboard_stats(request.merchant_shop)
    return render(request, "dashboard/home.html", {
        "shop": request.merchant_shop,
        "stats": stats,
    })


@merchant_required
def check_notifications(request):
    """
    Endpoint de polling HTMX — retourne un partial HTML avec les nouvelles
    commandes depuis le dernier check. Appelé toutes les 15s par le
    dashboard pour afficher une toast quand une nouvelle commande arrive.
    """
    from datetime import datetime

    from orders.models import Order

    shop = request.merchant_shop
    since_iso = request.GET.get("since", "")
    try:
        since = datetime.fromisoformat(since_iso.replace("Z", "+00:00")) if since_iso else None
    except ValueError:
        since = None

    qs = Order.objects.filter(shop=shop)
    if since:
        qs = qs.filter(created_at__gt=since)
    else:
        # Premier check : ne renvoie rien, juste le timestamp courant
        from django.utils import timezone
        return render(request, "dashboard/partials/notifications.html", {
            "new_orders": [],
            "now_iso": timezone.now().isoformat(),
            "pending_count": shop.orders.filter(status=Order.Status.PENDING).count(),
        })

    new_orders = list(qs.order_by("-created_at")[:5])

    from django.utils import timezone
    return render(request, "dashboard/partials/notifications.html", {
        "new_orders": new_orders,
        "now_iso": timezone.now().isoformat(),
        "pending_count": shop.orders.filter(status=Order.Status.PENDING).count(),
    })


# Vue historique conservée pour compatibilité du dispatcher
dashboard_redirect = dashboard_home
