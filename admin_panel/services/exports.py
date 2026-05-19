"""Exports CSV streamés pour l'admin.

On utilise StreamingHttpResponse + un générateur pour ne pas charger
toute la liste en mémoire — utile dès qu'on a quelques milliers de
lignes (commissions cross-boutique sur 1 an = plusieurs MB).

Extrait de admin_panel/views.py pour rendre la logique testable
unitairement (au lieu de devoir monter une réponse HTTP).
"""
import csv
from collections.abc import Iterable, Iterator

from django.db.models import QuerySet
from django.http import StreamingHttpResponse
from django.utils import timezone

from commissions.models import Commission


class _CSVEcho:
    """File-like qui yield au lieu d'écrire — pour CSV streaming.

    csv.writer attend un .write() ; on lui passe cet objet et chaque
    appel à .write() retourne la ligne, qu'on yield au générateur.
    """

    def write(self, value: str) -> str:
        return value


COMMISSIONS_CSV_COLUMNS = [
    "Référence commande", "Boutique", "Slug", "Commerçant", "Email",
    "Date", "Vente XOF", "Taux %", "Commission XOF", "À reverser XOF",
    "Reversé", "Date reversement", "Référence virement",
]


def _commission_to_row(c: Commission) -> list:
    """Convertit une Commission en ligne CSV."""
    return [
        c.order.reference,
        c.shop.name,
        c.shop.slug,
        c.shop.owner.username,
        c.shop.owner.email,
        c.created_at.strftime("%Y-%m-%d %H:%M"),
        c.sale_amount_xof,
        f"{c.rate}",
        c.commission_xof,
        c.merchant_amount_xof,
        "oui" if c.is_paid else "non",
        c.paid_at.strftime("%Y-%m-%d") if c.paid_at else "",
        c.payout_reference or "",
    ]


def filter_commissions_queryset(filter_state: str = "unpaid") -> QuerySet:
    """Filtre les commissions selon l'état (paid / unpaid / all)."""
    qs = Commission.objects.select_related(
        "order", "shop", "shop__owner",
    ).order_by("-created_at")
    if filter_state == "unpaid":
        qs = qs.filter(is_paid=False)
    elif filter_state == "paid":
        qs = qs.filter(is_paid=True)
    return qs


def commissions_csv_rows(qs: Iterable[Commission]) -> Iterator[str]:
    """Générateur qui yield les lignes CSV (header + body).

    À passer directement à StreamingHttpResponse. Utilise qs.iterator()
    en interne pour ne pas matérialiser tous les Commission en mémoire.
    """
    writer = csv.writer(_CSVEcho())
    yield writer.writerow(COMMISSIONS_CSV_COLUMNS)
    for c in qs.iterator():
        yield writer.writerow(_commission_to_row(c))


def stream_commissions_csv(filter_state: str = "unpaid") -> StreamingHttpResponse:
    """Vue helper : construit la StreamingHttpResponse complète prête à retourner."""
    qs = filter_commissions_queryset(filter_state)
    response = StreamingHttpResponse(
        commissions_csv_rows(qs),
        content_type="text/csv; charset=utf-8",
    )
    fname = (
        f"commissions_{filter_state}_"
        f"{timezone.now().strftime('%Y%m%d_%H%M')}.csv"
    )
    response["Content-Disposition"] = f'attachment; filename="{fname}"'
    return response
