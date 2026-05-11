"""Calcul de la progression d'onboarding d'une boutique.

Affiche au commerçant ce qui lui reste à faire pour avoir une boutique
prête à vendre. La checklist apparaît en haut du dashboard tant que les
6 étapes ne sont pas toutes complétées.

Étapes (toutes calculables sans nouveau champ en BDD) :
1. Compte créé          — toujours OK quand le shop existe
2. Description boutique — shop.description non vide (présentation pour le client)
3. Logo ajouté          — shop.logo défini (identité visuelle)
4. Catégories ajoutées  — au moins 1 catégorie active (via wizard catégories)
5. Premier produit      — au moins 1 produit actif (le déclencheur du switch
                          page coming-soon → vraie boutique côté public)
6. Zones de livraison   — au moins 1 DeliveryZone (sinon impossible de
                          livrer ailleurs qu'au retrait)

L'étape 5 est volontairement liée à la même condition que la page
coming-soon : si elle est cochée, la boutique apparaît publiquement.
"""
from dataclasses import dataclass


@dataclass
class OnboardingStep:
    key: str
    label: str
    done: bool
    url_name: str  # nom d'URL Django (résolu dans le template via {% url %})
    hint: str = ""


@dataclass
class OnboardingState:
    steps: list
    done_count: int
    total: int
    is_complete: bool

    @property
    def percent(self) -> int:
        if self.total == 0:
            return 100
        return round(100 * self.done_count / self.total)


def compute_onboarding(shop) -> OnboardingState:
    """Retourne l'état d'onboarding d'une boutique."""
    has_categories = shop.categories.filter(is_active=True).exists()
    has_products = shop.products.filter(is_active=True).exists()
    has_zones = shop.delivery_zones.exists() if hasattr(shop, "delivery_zones") else False

    steps = [
        OnboardingStep(
            key="account",
            label="Compte créé",
            done=True,
            url_name="shops_dashboard:settings",
            hint="Bienvenue sur Jappesi !",
        ),
        OnboardingStep(
            key="description",
            label="Description de ta boutique",
            done=bool((shop.description or "").strip()),
            url_name="shops_dashboard:settings",
            hint="Quelques mots pour présenter ce que tu vends.",
        ),
        OnboardingStep(
            key="logo",
            label="Logo ajouté",
            done=bool(shop.logo),
            url_name="shops_dashboard:settings",
            hint="Donne une identité visuelle à ta boutique.",
        ),
        OnboardingStep(
            key="categories",
            label="Catégories ajoutées",
            done=has_categories,
            url_name="products_dashboard:category_list",
            hint="Organise tes produits par univers (mode, beauté, alimentation…).",
        ),
        OnboardingStep(
            key="first_product",
            label="Premier produit ajouté",
            done=has_products,
            url_name="products_dashboard:suggestions",
            hint="Ta boutique devient publique dès le 1er produit. Utilise les idées prêtes.",
        ),
        OnboardingStep(
            key="delivery",
            label="Zones de livraison",
            done=has_zones,
            url_name="delivery_dashboard:list",
            hint="Définis où tu livres et à quels tarifs.",
        ),
    ]

    done_count = sum(1 for s in steps if s.done)
    total = len(steps)
    return OnboardingState(
        steps=steps,
        done_count=done_count,
        total=total,
        is_complete=done_count == total,
    )
