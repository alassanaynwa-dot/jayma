"""
Middleware multi-tenant Jappesi.

Détecte le sous-domaine dans la requête et bascule sur le bon urls.py :
- jappesi.sn                  → config.urls_public       (landing, auth)
- dashboard.jappesi.sn        → config.urls_dashboard    (commerçant)
- admin.jappesi.sn            → config.urls_admin        (plateforme)
- <slug>.jappesi.sn           → config.urls_shop         (boutique + request.shop)

Approche Django idiomatique : on set request.urlconf = "<module>" avant
que le URL resolver ne s'exécute. Chaque tenant a son propre set d'URLs.
"""
from django.conf import settings
from django.core.cache import cache
from django.http import Http404
from django.shortcuts import render


# Sous-domaines réservés qui ne correspondent pas à des boutiques
RESERVED_SUBDOMAINS = {
    "www",
    "dashboard",
    "admin",
    "api",
    "static",
    "media",
    "mail",
    "ftp",
    "blog",
    "help",
    "support",
}


class TenantMiddleware:
    """
    Pose sur la requête :
    - request.subdomain       : "" | "dashboard" | "admin" | "<shop-slug>"
    - request.shop            : instance Shop ou None
    - request.tenant_type     : "public" | "dashboard" | "admin" | "shop"
    - request.urlconf         : module URLs à utiliser
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(":")[0].lower()
        subdomain = self._extract_subdomain(host)

        request.subdomain = subdomain
        request.shop = None
        request.tenant_type = "public"
        request.urlconf = "config.urls_public"

        if subdomain == "dashboard":
            request.tenant_type = "dashboard"
            request.urlconf = "config.urls_dashboard"

        elif subdomain == "admin":
            request.tenant_type = "admin"
            request.urlconf = "config.urls_admin"

        elif subdomain and subdomain not in RESERVED_SUBDOMAINS:
            shop = self._load_shop(subdomain)
            if shop is None:
                raise Http404(f"Boutique '{subdomain}' introuvable.")

            if not shop.is_approved:
                return render(
                    request,
                    "shops/pending_approval.html",
                    {"shop": shop},
                    status=403,
                )

            if not shop.is_active:
                return render(
                    request,
                    "shops/inactive.html",
                    {"shop": shop},
                    status=403,
                )

            request.shop = shop
            request.tenant_type = "shop"
            request.urlconf = "config.urls_shop"

        return self.get_response(request)

    # Domaines racines reconnus — le middleware accepte tous ceux-ci
    # en parallèle (utile en dev où on switche entre .localhost et
    # .jayma.local selon l'historique des bookmarks).
    KNOWN_ROOTS = ("localhost", "jayma.local", "jappesi.sn")

    def _extract_subdomain(self, host: str) -> str:
        """
        Retourne le sous-domaine (ex: 'dashboard', 'demo') ou '' si pas de
        sous-domaine. On teste plusieurs roots connus pour que
        admin.localhost ET admin.jayma.local donnent le même résultat.
        """
        if host in ("localhost", "127.0.0.1") or host.startswith("127."):
            return ""

        # Roots à tester : d'abord celui configuré, puis les fallbacks
        configured = settings.JAYMA_ROOT_DOMAIN.lower()
        roots = [configured] + [r for r in self.KNOWN_ROOTS if r != configured]

        for root in roots:
            if host == root:
                return ""
            if host.endswith("." + root):
                prefix = host[: -(len(root) + 1)]
                # "www.maboutique" → on prend juste "maboutique"
                if "." in prefix:
                    prefix = prefix.rsplit(".", 1)[-1]
                return prefix

        return ""

    def _load_shop(self, slug: str):
        """Charge un Shop depuis le cache Redis ou la DB (TTL 5 min)."""
        cache_key = f"shop:slug:{slug}"
        shop = cache.get(cache_key)
        if shop is not None:
            return shop

        from shops.models import Shop

        try:
            shop = Shop.objects.select_related("owner").get(slug=slug)
        except Shop.DoesNotExist:
            return None

        cache.set(cache_key, shop, timeout=300)
        return shop
