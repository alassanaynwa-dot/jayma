"""Template tag : icônes SVG pour les catégories sur la boutique publique.

Pourquoi des SVG plutôt que des emojis :
- Les emojis sont rendus différemment selon l'OS (Apple/Google/Windows) → look
  incohérent
- Les emojis ont un côté "cheap" qui ne convient pas à un site e-commerce
  sérieux
- Les SVG outline restent cohérents partout, utilisent la couleur boutique
  (currentColor) et donnent un look pro / moderne

Usage dans un template :
    {% load category_icons %}
    <div class="text-jappesi-600">
      {{ category|category_icon|safe }}
    </div>

Le filtre cherche un SVG par :
1. Le slug exact de la catégorie (mode-femme, beaute-cheveux, …)
2. Le slug de son parent (si c'est une sous-catégorie)
3. Sinon, l'icône fallback générique

Toutes les icônes sont des paths Heroicons outline 24x24 (MIT). Format :
    <svg ... viewBox="0 0 24 24" stroke="currentColor" fill="none">
      <path .../>
    </svg>

On peut ajouter / modifier les SVG ici sans toucher aux modèles BDD.
"""
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


# Format commun à toutes les icônes : on définit juste les `<path>` SVG,
# la balise <svg> est ajoutée par _wrap_svg() avec les bons attributs.
_SVG_ATTRS = (
    'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" '
    'class="h-full w-full"'
)


def _wrap(paths: str) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" {_SVG_ATTRS}>{paths}</svg>'


# Mapping slug → SVG. Les slugs viennent de slugify(label) dans le wizard
# CATEGORY_TEMPLATES, donc :
#   "Mode femme" → "mode-femme"
#   "Beauté & cheveux" → "beaute-cheveux"
#   etc.
ICONS = {
    # Mode femme — robe / dress silhouette
    "mode-femme": _wrap(
        '<path d="M9 4h6m-6 0c0 2-1 3-1 5l-3 7c0 1 1 2 2 2h10c1 0 2-1 2-2l-3-7c0-2-1-3-1-5"/>'
        '<path d="M9 4l-1 2m7-2l1 2"/>'
    ),
    # Mode homme — chemise + cravate
    "mode-homme": _wrap(
        '<path d="M8 4l4 3 4-3M5 8l3-4h8l3 4M5 8v12h14V8M5 8L4 12M19 8l1 4M11 7l1 4 1-4"/>'
    ),
    # Mode enfant & bébé — biberon / silhouette enfant
    "mode-enfant-bebe": _wrap(
        '<path d="M10 3h4M9 3v3h6V3M9 6l-1 4v9a2 2 0 002 2h4a2 2 0 002-2v-9l-1-4"/>'
        '<path d="M10 12h4"/>'
    ),
    # Chaussures
    "chaussures": _wrap(
        '<path d="M3 18l1-7c0-1 1-2 2-2h2l4-3 5 5 5 1c1 0 2 1 2 2v2c0 1-1 2-2 2H4c-1 0-1-1-1-1z"/>'
        '<path d="M9 11l3 1m-3 4h12"/>'
    ),
    # Beauté & cheveux — flacon parfum
    "beaute-cheveux": _wrap(
        '<path d="M10 3h4v3h-4z"/>'
        '<path d="M9 6h6v2c1 0 2 1 2 2v9a2 2 0 01-2 2H9a2 2 0 01-2-2v-9c0-1 1-2 2-2V6z"/>'
        '<path d="M10 13h4"/>'
    ),
    # Accessoires — sac à main
    "accessoires": _wrap(
        '<path d="M5 9h14v11a1 1 0 01-1 1H6a1 1 0 01-1-1V9z"/>'
        '<path d="M9 9V7a3 3 0 016 0v2"/>'
    ),
    # Maison & déco — maison
    "maison-deco": _wrap(
        '<path d="M3 11l9-7 9 7v9a2 2 0 01-2 2H5a2 2 0 01-2-2v-9z"/>'
        '<path d="M9 21V13h6v8"/>'
    ),
    # Électronique — smartphone
    "electronique": _wrap(
        '<rect x="7" y="3" width="10" height="18" rx="2"/>'
        '<path d="M11 18h2"/>'
    ),
    # Alimentation & traditions — pot / jar
    "alimentation-traditions": _wrap(
        '<path d="M7 4h10l-1 3H8z"/>'
        '<path d="M8 7h8v12a2 2 0 01-2 2h-4a2 2 0 01-2-2V7z"/>'
        '<path d="M10 12h4M10 16h4"/>'
    ),
    # Loisirs & cadeaux — cadeau
    "loisirs-cadeaux": _wrap(
        '<rect x="4" y="9" width="16" height="11" rx="1"/>'
        '<path d="M4 13h16M12 9v11"/>'
        '<path d="M8 9c0-2 2-3 4-3 0 0-2-3-4-3s-3 1-3 3 3 3 3 3z"/>'
        '<path d="M16 9c0-2-2-3-4-3 0 0 2-3 4-3s3 1 3 3-3 3-3 3z"/>'
    ),
}

FALLBACK_ICON = _wrap(
    # Pictogramme dossier neutre pour les catégories custom hors wizard
    '<path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V7z"/>'
)


@register.filter
def category_icon(category) -> str:
    """Renvoie le SVG correspondant à la catégorie (par slug, puis parent slug, puis fallback)."""
    if not category:
        return mark_safe(FALLBACK_ICON)
    slug = getattr(category, "slug", "") or ""
    if slug in ICONS:
        return mark_safe(ICONS[slug])
    parent = getattr(category, "parent", None)
    if parent and getattr(parent, "slug", "") in ICONS:
        return mark_safe(ICONS[parent.slug])
    return mark_safe(FALLBACK_ICON)


# Mapping universe_key (utilisé dans CATEGORY_TEMPLATES et PRODUCT_SUGGESTIONS)
# vers le slug correspondant dans ICONS. C'est nécessaire parce que le wizard
# utilise des keys snake_case (mode_femme) alors que les slugs en BDD sont
# kebab-case (mode-femme).
UNIVERSE_KEY_TO_SLUG = {
    "mode_femme": "mode-femme",
    "mode_homme": "mode-homme",
    "mode_enfant": "mode-enfant-bebe",
    "chaussures": "chaussures",
    "beaute": "beaute-cheveux",
    "accessoires": "accessoires",
    "maison": "maison-deco",
    "electronique": "electronique",
    "alimentation": "alimentation-traditions",
    "loisirs": "loisirs-cadeaux",
}


@register.filter
def universe_icon(universe_key) -> str:
    """Icône SVG pour une clé d'univers (mode_femme, beaute, etc.).

    Utilisé dans le dashboard (wizard catégories, suggestions produits) où
    on manipule des dicts CATEGORY_TEMPLATES / PRODUCT_SUGGESTIONS plutôt
    que des modèles Category.
    """
    if not universe_key:
        return mark_safe(FALLBACK_ICON)
    slug = UNIVERSE_KEY_TO_SLUG.get(universe_key, "")
    if slug in ICONS:
        return mark_safe(ICONS[slug])
    return mark_safe(FALLBACK_ICON)
