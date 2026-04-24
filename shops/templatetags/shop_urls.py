"""Template tags pour générer des URLs de boutique cohérentes dev/prod."""
from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag(takes_context=True)
def shop_public_url(context, shop):
    """
    Retourne l'URL publique d'une boutique en se basant sur le host courant
    (scheme + port dynamiques). En prod ça donnera
    https://<slug>.jappesi.sn, en dev http://<slug>.localhost:8002.
    """
    request = context.get("request")
    if request is None:
        return f"https://{shop.slug}.{settings.JAYMA_ROOT_DOMAIN}"

    host = request.get_host()
    scheme = "https" if request.is_secure() else "http"
    port = ":" + host.split(":", 1)[1] if ":" in host else ""
    return f"{scheme}://{shop.slug}.{settings.JAYMA_ROOT_DOMAIN}{port}"


@register.simple_tag(takes_context=True)
def shop_public_host(context, shop):
    """Juste le host pour affichage (ex: chez-fatou.jappesi.sn ou chez-fatou.localhost:8002)."""
    request = context.get("request")
    port = ""
    if request is not None:
        host = request.get_host()
        port = ":" + host.split(":", 1)[1] if ":" in host else ""
    return f"{shop.slug}.{settings.JAYMA_ROOT_DOMAIN}{port}"
