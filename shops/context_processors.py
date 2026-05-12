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
    """Expose les URLs de la plateforme (root + sous-domaines principaux).

    Les clés `jappesi_*_url` sont les noms officiels depuis le rebrand.
    Les clés `jayma_*_url` sont conservées comme alias rétro-compatibles
    (1 release) pour que les templates existants continuent de marcher
    sans modification ; à supprimer dans la release suivante.
    """
    host = request.get_host()
    scheme = "https" if request.is_secure() else "http"
    port = ":" + host.split(":", 1)[1] if ":" in host else ""
    root = settings.JAPPESI_ROOT_DOMAIN

    root_url = f"{scheme}://{root}{port}"
    dashboard_url = f"{scheme}://dashboard.{root}{port}"
    admin_url = f"{scheme}://admin.{root}{port}"

    return {
        "jappesi_root_url":      root_url,
        "jappesi_dashboard_url": dashboard_url,
        "jappesi_admin_url":     admin_url,
        # Alias rétro-compatibles
        "jayma_root_url":      root_url,
        "jayma_dashboard_url": dashboard_url,
        "jayma_admin_url":     admin_url,
    }
