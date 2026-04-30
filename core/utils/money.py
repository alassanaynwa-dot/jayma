"""Helpers monétaires Jappesi.

Pour l'instant, monnaie unique : XOF (Franc CFA Afrique de l'Ouest).
Tout est entier (pas de centimes — la subdivision n'est pas utilisée
en pratique au Sénégal).

Si on supporte d'autres monnaies un jour (NGN, GHS, USD…), refactorer
``format_amount`` pour prendre une devise en paramètre.
"""
from __future__ import annotations

THOUSAND_SEP = " "  # espace régulière (compatible terminal, copy-paste, exports CSV)
DECIMAL_SEP = ","


def format_xof(value: int | None, *, with_currency: bool = True) -> str:
    """Formate un montant XOF avec séparateur de milliers.

    >>> format_xof(10000)
    '10 000 XOF'
    >>> format_xof(1500000)
    '1 500 000 XOF'
    >>> format_xof(0)
    '0 XOF'
    >>> format_xof(None)
    ''
    >>> format_xof(10000, with_currency=False)
    '10 000'
    """
    if value is None:
        return ""
    n = int(value)
    sign = "-" if n < 0 else ""
    n = abs(n)
    # Insère un séparateur tous les 3 chiffres en partant de la droite
    parts = []
    s = str(n)
    while len(s) > 3:
        parts.append(s[-3:])
        s = s[:-3]
    parts.append(s)
    formatted = sign + THOUSAND_SEP.join(reversed(parts))
    if with_currency:
        return f"{formatted}{THOUSAND_SEP}XOF"
    return formatted
