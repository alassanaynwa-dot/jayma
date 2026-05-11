"""Context processors — exposent shop + URLs de la plateforme aux templates."""
from django.conf import settings


def current_shop(request):
    """Injecte shop, tenant_type et subdomain dans le contexte des templates.

    Sur les sous-domaines boutique (<slug>.jappesi.sn), shop vient de
    request.shop (résolu par TenantMiddleware via le slug).
    Sur le dashboard (dashboard.jappesi.sn), shop vient de
    request.merchant_shop (la boutique du commerçant connecté). Permet
    aux templates dashboard d'utiliser {% if shop %} sans avoir à passer
    shop explicitement dans chaque vue (notamment pour la checklist
    d'onboarding).
    """
    shop = getattr(request, "shop", None) or getattr(request, "merchant_shop", None)
    return {
        "shop": shop,
        "tenant_type": getattr(request, "tenant_type", "public"),
        "subdomain": getattr(request, "subdomain", ""),
    }


def jayma_urls(request):
    """
    Expose les URLs de la plateforme (sans sous-domaine et avec sous-domaines
    principaux), calculées dynamiquement à partir du host courant.
    """
    host = request.get_host()
    scheme = "https" if request.is_secure() else "http"
    port = ":" + host.split(":", 1)[1] if ":" in host else ""
    root = settings.JAYMA_ROOT_DOMAIN

    return {
        "jayma_root_url":      f"{scheme}://{root}{port}",
        "jayma_dashboard_url": f"{scheme}://dashboard.{root}{port}",
        "jayma_admin_url":     f"{scheme}://admin.{root}{port}",
    }
