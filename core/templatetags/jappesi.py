"""Filtres et tags Django spécifiques à Jappesi.

Usage dans un template :
    {% load jappesi %}
    {{ order.total_xof|xof }}              {# → "10 000 XOF" #}
    {{ order.total_xof|xof:"no-currency" }} {# → "10 000" #}
"""
from __future__ import annotations

from django import template

from core.utils.money import format_xof

register = template.Library()


@register.filter(name="xof")
def xof_filter(value, mode: str = "") -> str:
    """Formate un entier XOF avec séparateur de milliers (espace).

    Si l'argument est "no-currency", omet le suffixe "XOF" (utile dans des
    contextes où la devise est déjà affichée en colonne ou en label).
    """
    return format_xof(value, with_currency=(mode != "no-currency"))
