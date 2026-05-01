"""Templates de catégories pour onboarding commerçant.

10 univers principaux + sous-catégories adaptées au marché sénégalais.
Utilisés par le wizard d'onboarding (products.views.category_wizard) qui copie
les sous-catégories sélectionnées dans la boutique du commerçant.

Garder ces templates en dur dans le code (vs un modèle Django) permet :
- Versioning Git (l'évolution de l'arborescence est tracée)
- Pas d'admin à maintenir
- Pas de seed BDD nécessaire au déploiement

Si on veut un jour faire de la **recherche cross-boutiques** par catégorie
unifiée (ex : "tous les bissap de toutes les boutiques"), on migrera vers
un modèle CategoryTemplate persistant. Pour l'instant, KISS.
"""

CATEGORY_TEMPLATES = [
    {
        "key": "mode_femme",
        "label": "Mode femme",
        "emoji": "👗",
        "description": "Robes, boubous, tenues de soirée…",
        "subcategories": [
            "Robes & tenues",
            "Boubous & bazin",
            "Hauts & chemisiers",
            "Pantalons & jupes",
            "Tenues de soirée",
            "Sous-vêtements & lingerie",
            "Maillots de bain",
            "Pyjamas & homewear",
            "Tenues traditionnelles",
            "Tenues de mariage",
            "Hijabs & voiles",
            "Caftans",
        ],
    },
    {
        "key": "mode_homme",
        "label": "Mode homme",
        "emoji": "👔",
        "description": "Boubous, chemises, costumes…",
        "subcategories": [
            "Boubous & grands boubous",
            "Chemises & polos",
            "Pantalons & jeans",
            "T-shirts & débardeurs",
            "Costumes & vestes",
            "Sous-vêtements",
            "Pyjamas & homewear",
            "Tenues traditionnelles",
        ],
    },
    {
        "key": "mode_enfant",
        "label": "Mode enfant & bébé",
        "emoji": "👶",
        "description": "Vêtements, puériculture, accessoires…",
        "subcategories": [
            "Couches, lait & soins bébé",
            "Vêtements bébé 0-2 ans",
            "Vêtements fille 3-12 ans",
            "Vêtements garçon 3-12 ans",
            "Tenues ado fille",
            "Tenues ado garçon",
            "Tenues traditionnelles enfant",
            "Chaussures enfant",
            "Accessoires enfant",
            "Poussettes & cosy",
        ],
    },
    {
        "key": "chaussures",
        "label": "Chaussures",
        "emoji": "👟",
        "description": "Sneakers, sandales, escarpins, babouches…",
        "subcategories": [
            "Sneakers & baskets",
            "Sandales & tongs",
            "Escarpins & talons",
            "Mocassins & derbies",
            "Babouches & weston",
            "Boots & bottines",
            "Chaussures de sport",
            "Chaussures de travail",
            "Chaussures enfant",
            "Chaussons & pantoufles",
        ],
    },
    {
        "key": "beaute",
        "label": "Beauté & cheveux",
        "emoji": "💄",
        "description": "Parfums, soins, perruques, maquillage…",
        "subcategories": [
            "Parfums femme",
            "Parfums homme",
            "Soins du visage",
            "Soins du corps",
            "Maquillage",
            "Hygiène intime",
            "Déodorants & anti-transpirants",
            "Méchès & extensions",
            "Tissages",
            "Perruques",
            "Soins capillaires",
            "Défrisants & relaxants",
            "Coiffure traditionnelle",
            "Outils coiffure",
        ],
    },
    {
        "key": "accessoires",
        "label": "Accessoires",
        "emoji": "💍",
        "description": "Sacs, bijoux, ceintures, lunettes…",
        "subcategories": [
            "Sacs à main & pochettes",
            "Bijoux & montres",
            "Ceintures & écharpes",
            "Lunettes de soleil",
            "Casquettes & chapeaux",
            "Maroquinerie",
            "Valises & bagages",
            "Ombrelles & parapluies",
        ],
    },
    {
        "key": "maison",
        "label": "Maison & déco",
        "emoji": "🏠",
        "description": "Linge, déco, cuisine, luminaires…",
        "subcategories": [
            "Linge de maison",
            "Déco intérieure",
            "Cuisine & arts de la table",
            "Rangement & organisation",
            "Luminaires",
            "Tapis & rideaux",
            "Accessoires salle de bain",
            "Plantes & jardinage",
        ],
    },
    {
        "key": "electronique",
        "label": "Électronique",
        "emoji": "📱",
        "description": "Téléphones, écouteurs, chargeurs, TV…",
        "subcategories": [
            "Téléphones & smartphones",
            "Coques & protections",
            "Écouteurs & casques",
            "Enceintes Bluetooth",
            "Câbles & chargeurs",
            "Powerbanks & batteries",
            "Ordinateurs & accessoires",
            "TV & accessoires",
        ],
    },
    {
        "key": "alimentation",
        "label": "Alimentation & traditions",
        "emoji": "🍯",
        "description": "Épices, thé, hibiscus, produits islamiques…",
        "subcategories": [
            "Épices & condiments",
            "Thé, café & boissons",
            "Hibiscus & superaliments",
            "Dattes, miel & beurre de karité",
            "Encens & parfums non-alcoolisés",
            "Tapis de prière & accessoires",
            "Chapelets & livres religieux",
            "Compléments naturels",
        ],
    },
    {
        "key": "loisirs",
        "label": "Loisirs & cadeaux",
        "emoji": "🎁",
        "description": "Sport, jouets, fournitures, cadeaux…",
        "subcategories": [
            "Sport & fitness",
            "Jouets & jeux enfants",
            "Fournitures scolaires",
            "Cadeaux personnalisés",
            "Articles de mariage",
            "Décoration événementielle",
        ],
    },
]


def get_template_by_key(key: str) -> dict | None:
    """Retourne le template d'univers correspondant à la clé, ou None."""
    for tpl in CATEGORY_TEMPLATES:
        if tpl["key"] == key:
            return tpl
    return None


def total_subcategories() -> int:
    """Nombre total de sous-catégories disponibles dans le catalogue."""
    return sum(len(t["subcategories"]) for t in CATEGORY_TEMPLATES)
