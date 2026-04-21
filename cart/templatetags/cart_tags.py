"""Template tags pour le panier."""
from django import template

from cart.services.cart import Cart

register = template.Library()


@register.simple_tag(takes_context=True)
def cart_count(context):
    """Nombre d'items dans le panier session."""
    request = context.get("request")
    if not request:
        return 0
    return len(Cart(request))


@register.simple_tag(takes_context=True)
def cart_total(context):
    """Total XOF du panier."""
    request = context.get("request")
    if not request:
        return 0
    return Cart(request).total_xof
