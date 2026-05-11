"""Template tag qui injecte la checklist d'onboarding dans dashboard/base.html.

Usage :
    {% load onboarding_tags %}
    {% onboarding_checklist shop %}

La tag rend le partial dashboard/partials/_onboarding_checklist.html avec
le contexte calculé. Elle ne fait rien si le shop est None ou si la
checklist est complète (l'utilisateur a tout fini).
"""
from django import template

from shops.services.onboarding import compute_onboarding

register = template.Library()


@register.inclusion_tag("dashboard/partials/_onboarding_checklist.html")
def onboarding_checklist(shop):
    """Rend la checklist si shop a des étapes en cours, sinon ne rend rien."""
    if shop is None:
        return {"onboarding": None}
    state = compute_onboarding(shop)
    if state.is_complete:
        # Checklist 100% → on cache complètement
        return {"onboarding": None}
    return {"onboarding": state}
