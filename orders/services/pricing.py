"""Calculs des montants de commande (commission, total)."""
from decimal import Decimal


def compute_commission(amount_xof: int, rate_percent) -> tuple[int, int]:
    """
    Calcule (commission_xof, merchant_amount_xof) à partir du total et du taux.

    Arrondi à l'entier inférieur pour la commission (la plateforme ne
    réclame jamais de fraction de FCFA). Le commerçant récupère le reste.
    """
    if amount_xof <= 0:
        return 0, 0
    rate = Decimal(rate_percent) / Decimal("100")
    commission = int(Decimal(amount_xof) * rate)  # arrondi vers zéro
    merchant = amount_xof - commission
    return commission, merchant
