"""Logique de matching zone <-> ville + calcul frais de livraison."""
from delivery.models import Courier, DeliveryZone


def find_zone_for(shop, city_or_area: str) -> DeliveryZone | None:
    """Retourne la première zone active de la boutique qui couvre cette ville."""
    if not city_or_area:
        return None
    for zone in shop.delivery_zones.filter(is_active=True).order_by("position", "name"):
        if zone.covers(city_or_area):
            return zone
    return None


def compute_delivery_fee(shop, city_or_area: str) -> tuple[int, DeliveryZone | None]:
    """Retourne (frais_xof, zone) pour une livraison dans une ville."""
    zone = find_zone_for(shop, city_or_area)
    if zone is None:
        return 0, None
    return zone.fee_xof, zone


def suggest_courier_for_order(order) -> Courier | None:
    """Trouve un livreur actif qui couvre la zone de la commande."""
    zone = find_zone_for(order.shop, order.client_city)
    if zone:
        return zone.couriers.filter(is_active=True).order_by("name").first()
    # Fallback : premier livreur actif
    return order.shop.couriers.filter(is_active=True).order_by("name").first()
