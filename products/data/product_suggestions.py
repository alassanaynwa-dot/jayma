"""Suggestions de produits pour onboarding commerçants — approche B.

Ne crée AUCUN produit en BDD. Le commerçant voit des idées (~50 produits
typiques au Sénégal), il clique « Créer ce produit » → le formulaire
de création est pré-rempli (nom, description, prix suggéré, catégorie
pré-sélectionnée si la boutique a importé l'univers via le wizard).

Le commerçant reste 100% en contrôle :
- Aucun produit fantôme dans la BDD
- Tous les champs restent modifiables
- Il doit ajouter sa propre image et ajuster avant publication

Format : liste plate de dicts. Le tri/filtre se fait dans la vue.
"""

PRODUCT_SUGGESTIONS = [
    # ============ Mode femme ============
    {
        "key": "boubou-brode-femme",
        "name": "Boubou brodé femme",
        "universe_key": "mode_femme",
        "suggested_category_slug": "boubous-bazin",
        "suggested_price": 20000,
        "description": "Boubou élégant en tissu bazin, broderies traditionnelles à la main. Disponible en plusieurs tailles et coloris.",
    },
    {
        "key": "robe-wax-cocktail",
        "name": "Robe wax cocktail",
        "universe_key": "mode_femme",
        "suggested_category_slug": "robes-tenues",
        "suggested_price": 15000,
        "description": "Robe en pagne wax aux motifs colorés, coupe ajustée pour soirée ou cérémonie.",
    },
    {
        "key": "caftan-moderne",
        "name": "Caftan moderne",
        "universe_key": "mode_femme",
        "suggested_category_slug": "caftans",
        "suggested_price": 25000,
        "description": "Caftan revisité avec broderies et perles, parfait pour les grandes occasions.",
    },
    {
        "key": "chemisier-wax",
        "name": "Chemisier wax femme",
        "universe_key": "mode_femme",
        "suggested_category_slug": "hauts-chemisiers",
        "suggested_price": 8000,
        "description": "Chemisier en tissu wax, manches longues. Idéal pour le travail ou le quotidien.",
    },
    {
        "key": "hijab-soie",
        "name": "Hijab voile en soie",
        "universe_key": "mode_femme",
        "suggested_category_slug": "hijabs-voiles",
        "suggested_price": 5000,
        "description": "Voile en soie légère, plusieurs coloris au choix. Doux et confortable.",
    },
    {
        "key": "tenue-mariage-3p",
        "name": "Tenue de mariage 3 pièces",
        "universe_key": "mode_femme",
        "suggested_category_slug": "tenues-mariage",
        "suggested_price": 80000,
        "description": "Ensemble complet pour cérémonie de mariage : robe, voile et accessoires assortis.",
    },

    # ============ Mode homme ============
    {
        "key": "grand-boubou-bazin",
        "name": "Grand boubou bazin riche",
        "universe_key": "mode_homme",
        "suggested_category_slug": "boubous-grands-boubous",
        "suggested_price": 35000,
        "description": "Grand boubou en bazin riche teint à la main. Tenue traditionnelle pour cérémonies.",
    },
    {
        "key": "chemise-lin-ete",
        "name": "Chemise en lin été",
        "universe_key": "mode_homme",
        "suggested_category_slug": "chemises-polos",
        "suggested_price": 12000,
        "description": "Chemise en lin léger, parfaite pour la chaleur. Coupe ajustée moderne.",
    },
    {
        "key": "costume-3-pieces",
        "name": "Costume 3 pièces",
        "universe_key": "mode_homme",
        "suggested_category_slug": "costumes-vestes",
        "suggested_price": 60000,
        "description": "Costume complet veste + pantalon + gilet. Tissu de qualité, finitions soignées.",
    },
    {
        "key": "polo-brode",
        "name": "Polo brodé homme",
        "universe_key": "mode_homme",
        "suggested_category_slug": "t-shirts-debardeurs",
        "suggested_price": 9000,
        "description": "Polo en coton avec broderie discrète. Plusieurs tailles et coloris disponibles.",
    },

    # ============ Mode enfant & bébé ============
    {
        "key": "pack-bebe-naissance",
        "name": "Pack bébé naissance",
        "universe_key": "mode_enfant",
        "suggested_category_slug": "couches-lait-soins-bebe",
        "suggested_price": 15000,
        "description": "Pack complet : pyjama, body, chaussons et bonnet pour nouveau-né. Coton bio.",
    },
    {
        "key": "tenue-bapteme-fille",
        "name": "Tenue baptême fille",
        "universe_key": "mode_enfant",
        "suggested_category_slug": "vetements-bebe-0-2-ans",
        "suggested_price": 18000,
        "description": "Tenue blanche cérémonie baptême avec dentelle et broderies. Pour fille 0-12 mois.",
    },
    {
        "key": "uniforme-ecole-garcon",
        "name": "Uniforme école garçon",
        "universe_key": "mode_enfant",
        "suggested_category_slug": "vetements-garcon-3-12-ans",
        "suggested_price": 7000,
        "description": "Chemise + short uniforme école primaire. Tissu résistant, lavable en machine.",
    },
    {
        "key": "tenue-korite-fille",
        "name": "Tenue korité fille",
        "universe_key": "mode_enfant",
        "suggested_category_slug": "tenues-traditionnelles-enfant",
        "suggested_price": 12000,
        "description": "Tenue traditionnelle pour la fête de korité, avec voile assorti. Tailles 4-12 ans.",
    },

    # ============ Chaussures ============
    {
        "key": "babouches-cuir",
        "name": "Babouches cuir homme",
        "universe_key": "chaussures",
        "suggested_category_slug": "babouches-weston",
        "suggested_price": 15000,
        "description": "Babouches en cuir véritable, finition artisanale. Confort exceptionnel.",
    },
    {
        "key": "sandales-tongs",
        "name": "Sandales tongs été",
        "universe_key": "chaussures",
        "suggested_category_slug": "sandales-tongs",
        "suggested_price": 5000,
        "description": "Sandales légères pour la plage ou le quotidien. Plusieurs coloris.",
    },
    {
        "key": "sneakers-running",
        "name": "Sneakers running",
        "universe_key": "chaussures",
        "suggested_category_slug": "sneakers-baskets",
        "suggested_price": 25000,
        "description": "Sneakers de course avec amorti, semelle antidérapante. Idéal sport et ville.",
    },
    {
        "key": "escarpins-talons",
        "name": "Escarpins talons hauts",
        "universe_key": "chaussures",
        "suggested_category_slug": "escarpins-talons",
        "suggested_price": 12000,
        "description": "Escarpins élégants à talons 8cm, parfaits pour soirée et bureau.",
    },

    # ============ Beauté & cheveux ============
    {
        "key": "parfum-oud-100ml",
        "name": "Parfum Oud premium 100ml",
        "universe_key": "beaute",
        "suggested_category_slug": "parfums-femme",
        "suggested_price": 18000,
        "description": "Parfum oriental aux notes d'oud, vanille et musc. Tenue longue durée.",
    },
    {
        "key": "creme-visage",
        "name": "Crème éclaircissante visage",
        "universe_key": "beaute",
        "suggested_category_slug": "soins-du-visage",
        "suggested_price": 6000,
        "description": "Crème jour à base de karité et vitamine C. Unifie le teint.",
    },
    {
        "key": "beurre-karite-500g",
        "name": "Beurre de karité pur 500g",
        "universe_key": "beaute",
        "suggested_category_slug": "soins-du-corps",
        "suggested_price": 4500,
        "description": "Beurre de karité 100% pur du Burkina Faso. Hydratant intense corps et cheveux.",
    },
    {
        "key": "meches-humaines-14",
        "name": "Mèches cheveux humains 14\"",
        "universe_key": "beaute",
        "suggested_category_slug": "meches-extensions",
        "suggested_price": 35000,
        "description": "Mèches 100% cheveux humains, ondulés naturels. Pose longue durée.",
    },
    {
        "key": "perruque-bob",
        "name": "Perruque bob lacée",
        "universe_key": "beaute",
        "suggested_category_slug": "perruques",
        "suggested_price": 28000,
        "description": "Perruque bob avec dentelle frontale, cheveux humains, coupe moderne.",
    },
    {
        "key": "rouge-levres-mat",
        "name": "Rouge à lèvres mat longue tenue",
        "universe_key": "beaute",
        "suggested_category_slug": "maquillage",
        "suggested_price": 3500,
        "description": "Rouge à lèvres mat liquide, tenue 12h, plusieurs nuances.",
    },

    # ============ Accessoires ============
    {
        "key": "sac-cuir-femme",
        "name": "Sac à main cuir véritable",
        "universe_key": "accessoires",
        "suggested_category_slug": "sacs-main-pochettes",
        "suggested_price": 22000,
        "description": "Sac à main en cuir véritable, plusieurs compartiments, élégant et solide.",
    },
    {
        "key": "montre-doree",
        "name": "Montre dorée femme",
        "universe_key": "accessoires",
        "suggested_category_slug": "bijoux-montres",
        "suggested_price": 15000,
        "description": "Montre tendance bracelet doré, mouvement quartz, étanche.",
    },
    {
        "key": "lunettes-soleil-aviateur",
        "name": "Lunettes de soleil aviateur",
        "universe_key": "accessoires",
        "suggested_category_slug": "lunettes-de-soleil",
        "suggested_price": 8000,
        "description": "Lunettes style aviateur, protection UV400, monture métal.",
    },
    {
        "key": "casquette-brodee",
        "name": "Casquette brodée logo",
        "universe_key": "accessoires",
        "suggested_category_slug": "casquettes-chapeaux",
        "suggested_price": 5000,
        "description": "Casquette ajustable, broderie soignée, tissu coton.",
    },

    # ============ Maison & déco ============
    {
        "key": "drap-wax-2-places",
        "name": "Drap brodé wax 2 places",
        "universe_key": "maison",
        "suggested_category_slug": "linge-de-maison",
        "suggested_price": 25000,
        "description": "Parure de lit 2 places en wax avec broderies. 1 drap + 2 taies d'oreiller.",
    },
    {
        "key": "vaisselle-artisanale",
        "name": "Vaisselle artisanale set",
        "universe_key": "maison",
        "suggested_category_slug": "cuisine-arts-de-la-table",
        "suggested_price": 12000,
        "description": "Set de 6 assiettes en céramique peinte main. Vaisselle exclusive Sénégal.",
    },
    {
        "key": "lampe-verre-artisanale",
        "name": "Lampe artisanale en verre",
        "universe_key": "maison",
        "suggested_category_slug": "luminaires",
        "suggested_price": 18000,
        "description": "Lampe de table en verre soufflé à la main. Lumière chaleureuse.",
    },

    # ============ Électronique ============
    {
        "key": "ecouteurs-bluetooth",
        "name": "Écouteurs Bluetooth sans fil",
        "universe_key": "electronique",
        "suggested_category_slug": "ecouteurs-casques",
        "suggested_price": 12000,
        "description": "Écouteurs Bluetooth 5.0, autonomie 6h + 24h avec étui. Son qualité HD.",
    },
    {
        "key": "powerbank-20000",
        "name": "Powerbank 20000 mAh",
        "universe_key": "electronique",
        "suggested_category_slug": "powerbanks-batteries",
        "suggested_price": 15000,
        "description": "Batterie externe 20000 mAh, 2 ports USB, charge rapide.",
    },
    {
        "key": "cable-usbc-2m",
        "name": "Câble USB-C 2m renforcé",
        "universe_key": "electronique",
        "suggested_category_slug": "cables-chargeurs",
        "suggested_price": 3500,
        "description": "Câble USB-C 2m tressé nylon, charge rapide, durable.",
    },
    {
        "key": "coque-iphone",
        "name": "Coque iPhone protection",
        "universe_key": "electronique",
        "suggested_category_slug": "coques-protections",
        "suggested_price": 5000,
        "description": "Coque silicone antichoc pour iPhone, plusieurs couleurs.",
    },

    # ============ Alimentation & traditions ============
    {
        "key": "bissap-500g",
        "name": "Bissap sec premium 500g",
        "universe_key": "alimentation",
        "suggested_category_slug": "hibiscus-superaliments",
        "suggested_price": 4000,
        "description": "Hibiscus séché du Sénégal, qualité premium. Pour boissons et infusions.",
    },
    {
        "key": "dattes-medjool-1kg",
        "name": "Dattes Medjool 1kg",
        "universe_key": "alimentation",
        "suggested_category_slug": "dattes-miel-beurre-de-karite",
        "suggested_price": 12000,
        "description": "Dattes Medjool premium d'Algérie, charnues et sucrées. Idéales pour iftar.",
    },
    {
        "key": "encens-bakhour",
        "name": "Encens Bakhour Oud",
        "universe_key": "alimentation",
        "suggested_category_slug": "encens-parfums-non-alcoolises",
        "suggested_price": 8000,
        "description": "Encens Bakhour parfum oud, à brûler sur charbon. Senteur intense.",
    },
    {
        "key": "tapis-priere-velours",
        "name": "Tapis de prière velours",
        "universe_key": "alimentation",
        "suggested_category_slug": "tapis-de-priere-accessoires",
        "suggested_price": 15000,
        "description": "Tapis de prière épais en velours, motifs traditionnels, doux au toucher.",
    },

    # ============ Loisirs & cadeaux ============
    {
        "key": "ballon-football",
        "name": "Ballon de football taille 5",
        "universe_key": "loisirs",
        "suggested_category_slug": "sport-fitness",
        "suggested_price": 8000,
        "description": "Ballon de football officiel taille 5, qualité match.",
    },
    {
        "key": "jouet-educatif",
        "name": "Jouet éducatif Montessori",
        "universe_key": "loisirs",
        "suggested_category_slug": "jouets-jeux-enfants",
        "suggested_price": 10000,
        "description": "Jeu éducatif en bois, méthode Montessori, pour enfants 3-7 ans.",
    },
    {
        "key": "cadeau-personnalise",
        "name": "Mug personnalisé photo",
        "universe_key": "loisirs",
        "suggested_category_slug": "cadeaux-personnalises",
        "suggested_price": 6000,
        "description": "Mug personnalisé avec photo et texte. Idéal cadeau anniversaire.",
    },
]


def get_suggestion_by_key(key: str) -> dict | None:
    """Retourne la suggestion correspondant à la clé, ou None."""
    for s in PRODUCT_SUGGESTIONS:
        if s["key"] == key:
            return s
    return None


def suggestions_by_universe() -> dict[str, list[dict]]:
    """Groupe les suggestions par universe_key (utile pour l'affichage filtré)."""
    result: dict[str, list[dict]] = {}
    for s in PRODUCT_SUGGESTIONS:
        result.setdefault(s["universe_key"], []).append(s)
    return result
