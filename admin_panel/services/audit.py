"""Helper unique pour journaliser une action admin."""
from typing import Any

from admin_panel.models import AdminAction


def log_admin_action(
    *,
    actor,
    action: str,
    target=None,
    target_repr: str = "",
    meta: dict[str, Any] | None = None,
) -> AdminAction:
    """Crée une entrée AdminAction. Signature claire et sûre (sans fail).

    `target` peut être un modèle Django ; on en extrait type + id. Sinon
    laisser vide et renseigner target_repr manuellement.
    """
    target_type = ""
    target_id = ""
    if target is not None:
        target_type = target.__class__.__name__
        target_id = str(getattr(target, "pk", ""))
        if not target_repr:
            target_repr = str(target)[:200]

    return AdminAction.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        target_repr=target_repr,
        meta=meta or {},
    )
