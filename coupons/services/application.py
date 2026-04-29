"""Application de coupons côté panier / checkout."""
from dataclasses import dataclass

from ..models import Coupon, CouponUsage

COUPON_SESSION_KEY = "coupon_code"


@dataclass
class CouponResult:
    coupon: Coupon | None
    discount_xof: int          # Remise sur le sous-total (hors livraison)
    freeship: bool = False     # True si le coupon offre la livraison
    error: str | None = None


def find_coupon(shop, code: str) -> Coupon | None:
    """Lookup case-insensitive d'un coupon pour cette boutique."""
    if not code:
        return None
    return shop.coupons.filter(code__iexact=code.strip()).first()


def try_apply_coupon(shop, code: str, subtotal_xof: int, client_phone: str = "") -> CouponResult:
    """Tente d'appliquer un coupon et retourne le résultat."""
    coupon = find_coupon(shop, code)
    if coupon is None:
        return CouponResult(None, 0, False, "Ce code promo n'existe pas.")
    if not coupon.is_valid_now():
        return CouponResult(None, 0, False, "Ce code promo n'est plus valide.")
    if subtotal_xof < coupon.min_order_xof:
        return CouponResult(
            None, 0, False,
            f"Ce code requiert un panier minimum de {coupon.min_order_xof} XOF.",
        )
    # Limite 1 utilisation par client (téléphone)
    if coupon.one_per_customer and client_phone:
        already = CouponUsage.objects.filter(
            coupon=coupon, client_phone=client_phone,
        ).exists()
        if already:
            return CouponResult(None, 0, False, "Tu as déjà utilisé ce code.")

    if coupon.is_freeship():
        return CouponResult(coupon, 0, freeship=True)

    discount = coupon.compute_discount(subtotal_xof)
    if discount <= 0:
        return CouponResult(None, 0, False, "Ce code ne s'applique pas à ton panier.")
    return CouponResult(coupon, discount, freeship=False)


# ============ Session helpers ============

def set_session_coupon(session, code: str) -> None:
    session[COUPON_SESSION_KEY] = code.upper().strip()
    session.modified = True


def get_session_coupon_code(session) -> str:
    return session.get(COUPON_SESSION_KEY, "")


def clear_session_coupon(session) -> None:
    if COUPON_SESSION_KEY in session:
        del session[COUPON_SESSION_KEY]
        session.modified = True


def compute_cart_discount(request, shop, subtotal_xof: int, client_phone: str = "") -> CouponResult:
    """Applique le coupon stocké en session et retourne le résultat."""
    code = get_session_coupon_code(request.session)
    if not code:
        return CouponResult(None, 0)
    return try_apply_coupon(shop, code, subtotal_xof, client_phone=client_phone)
