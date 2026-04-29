# Jappesi — Documentation projet

Documentation technique et fonctionnelle complète de la plateforme **Jappesi** : SaaS e-commerce multi-tenant pour le marché sénégalais.

> Cette doc est la **source de vérité** pour comprendre Jappesi de bout en bout. Pour des sujets ciblés :
>
> - **Setup VPS de zéro** → [`deploy/VPS_SETUP.md`](../deploy/VPS_SETUP.md)
> - **Runbook ops courantes** → [`deploy/README.md`](../deploy/README.md)
> - **Services tiers (URLs, comptes, secrets)** → [`deploy/SERVICES.md`](../deploy/SERVICES.md)

---

## Table des matières

1. [Présentation](#1-présentation)
2. [Stack technique](#2-stack-technique)
3. [Architecture multi-tenant](#3-architecture-multi-tenant)
4. [Settings & configuration](#4-settings--configuration)
5. [Modèles métier (apps Django)](#5-modèles-métier-apps-django)
6. [URLs & routing](#6-urls--routing)
7. [Workflows métier](#7-workflows-métier)
8. [Tâches asynchrones (Celery)](#8-tâches-asynchrones-celery)
9. [Frontend (templates, HTMX, Tailwind, PWA)](#9-frontend)
10. [Sécurité](#10-sécurité)
11. [Développement local](#11-développement-local)
12. [Production](#12-production)
13. [Dette technique & TODO](#13-dette-technique--todo)
14. [Lexique](#14-lexique)

---

## 1. Présentation

### Qu'est-ce que Jappesi

**Jappesi** (anciennement *Jayma*) est une plateforme SaaS de e-commerce **multi-tenant** ciblant les commerçants sénégalais. Chaque commerçant ouvre sa boutique en ligne sur un sous-domaine `<slug>.jappesi.sn`, sans toucher à du code ni à de l'hébergement.

Le mot *jappesi* signifie « apporter, donner » en wolof — l'idée du commerçant qui apporte ses produits jusqu'au client.

### À qui ça s'adresse

| Acteur | Ce qu'il fait |
|--------|---------------|
| **Commerçant** (merchant) | Ouvre sa boutique, gère catalogue, commandes, livraison, promos, livreurs |
| **Client final** | Achète sur la boutique d'un commerçant, paie en Wave/OM, suit sa livraison |
| **Admin plateforme** | Approuve les nouvelles boutiques, modère, suit les commissions, gère les outils transverses |
| **Livreur** | Affecté à une commande par le commerçant, livre, est noté par le client |

### Modèle économique

Jappesi prend une **commission de 8 %** (par défaut, paramétrable par boutique via `commission_rate`) sur chaque transaction réussie. Le reste est reversé au commerçant via les outils Wave/Orange Money/Banque.

Exemple sur une commande de 10 000 XOF :
- Le client paie 10 000 XOF (+ frais de livraison)
- Jappesi encaisse 800 XOF (8 %)
- Le commerçant reçoit 9 200 XOF lors du reversement

La commission est **figée à la création de la commande** (champ `Order.commission_rate` snapshot) pour qu'un changement de taux n'affecte pas les commandes en cours.

### Domaine et marque

- Domaine principal : **`jappesi.sn`** (production)
- Domaine secondaire : `jappesi.com` (parking)
- Email transactionnel : `noreply@jappesi.sn` (SendGrid)
- Email contact : `contact@jappesi.sn` (OVH Zimbra)
- Devise : XOF (Franc CFA), toujours **en entier** — pas de centimes

---

## 2. Stack technique

### Langages & frameworks

| Couche | Tech | Version |
|--------|------|---------|
| Backend | Django | 5.2 LTS (support jusqu'avril 2028) |
| Langage | Python | 3.12 (image Docker `python:3.12-slim`) |
| BDD | PostgreSQL | 16 (alpine) |
| Cache + queue | Redis | 7 (alpine) |
| Frontend CSS | Tailwind CSS | v4 (binaire CLI standalone) |
| Frontend JS | HTMX | 1.21+ |
| Async | Celery | 5.4+ (broker Redis) |
| Cron Celery | django-celery-beat | 2.8+ |
| Admin UI | django-unfold | 0.43+ |
| Static prod | WhiteNoise | 6.8+ |
| Serveur prod | gunicorn | 23+ (gthread workers) |
| Serveur dev | django runserver | — |
| Reverse proxy | nginx | 1.27 (alpine) |
| Stockage fichiers | Local volume **ou** Cloudflare R2 (S3-compatible) | — |
| SMS | AfricasTalking | 1.2+ (prod) ou ConsoleSMSBackend (dev) |
| Email | SendGrid SMTP | — |
| Monitoring | Sentry | 2.18+ |
| Paiements | Wave Business / Orange Money / CinetPay | — |
| Containerisation | Docker + docker compose | — |

### Arbre des dépendances Python

Voir [`requirements.txt`](../requirements.txt) (prod) et [`requirements-dev.txt`](../requirements-dev.txt) (dev — debug toolbar, pytest, etc.).

### Découpage Docker

**Dev** (`docker-compose.yml`) :
- `web` (Django runserver + Tailwind watch)
- `db` (Postgres, port 5434 exposé)
- `redis` (port 6381)
- `celery_worker`, `celery_beat`
- `mailpit` (SMTP capture pour dev)

**Prod** (`deploy/docker-compose.prod.yml`) :
- `web` (gunicorn 4 workers gthread)
- `db` (Postgres, **non exposé**)
- `redis` (non exposé)
- `celery_worker`, `celery_beat`
- `nginx` (80 + 443, terminaison TLS via Let's Encrypt)
- `certbot` (renouvellement automatique cert wildcard, sleep 12h)

---

## 3. Architecture multi-tenant

### Routing par sous-domaine

Jappesi gère **un seul domaine racine** (`jappesi.sn`) avec **routing dynamique selon le sous-domaine** :

| Sous-domaine | URLconf | Cible |
|--------------|---------|-------|
| `jappesi.sn` (apex) | `config.urls_public` | Landing, inscription commerçant, login, mentions légales |
| `dashboard.jappesi.sn` | `config.urls_dashboard` | Espace commerçant (catalogue, commandes, livreurs, promos…) |
| `admin.jappesi.sn` | `config.urls_admin` | Panneau admin Jappesi (approbation boutiques, modération) |
| `<slug>.jappesi.sn` | `config.urls_shop` | Boutique publique d'un commerçant donné |

Les sous-domaines `www, dashboard, admin, api, static, media, mail, ftp, blog, help, support` sont **réservés** : un commerçant ne peut pas avoir un slug qui les match.

### Le `TenantMiddleware`

Tout le dispatch est porté par un middleware custom : [`config/middleware.py`](../config/middleware.py). Pseudo-code :

```python
class TenantMiddleware:
    def __call__(self, request):
        host = request.get_host().lower().split(":")[0]
        subdomain = self._extract_subdomain(host)

        if subdomain in RESERVED_SUBDOMAINS:
            request.urlconf = f"config.urls_{subdomain}"  # admin / dashboard
        elif subdomain == "":
            request.urlconf = "config.urls_public"
        else:
            request.shop = self._get_shop_by_slug(subdomain)  # cache Redis 5min
            if request.shop is None:
                raise Http404
            request.urlconf = "config.urls_shop"

        return self.get_response(request)
```

### Cache des boutiques

Pour ne pas faire un SELECT à chaque requête sur tous les sous-domaines, le middleware met en cache l'objet `Shop` dans Redis sous la clé `shop:slug:{slug}` pendant 5 minutes.

Le cache est invalidé automatiquement par les **signaux Django** sur `Shop` :
- `post_save` → invalidation après modif
- `post_delete` → invalidation après suppression
- `pre_save` → invalidation aussi de l'ancien slug si modifié

### Isolation des données par tenant

C'est le **pilier sécuritaire** de la plateforme. Tous les modèles métier importants ont une **ForeignKey vers `Shop`** : `Product`, `Category`, `Order`, `OrderItem` (indirect), `Coupon`, `DeliveryZone`, `Courier`, `Commission`.

Toutes les vues du dashboard et de la boutique publique **filtrent systématiquement par `request.shop`** :

```python
# Dans une vue dashboard
products = Product.objects.filter(shop=request.user.shop)

# Dans une vue boutique publique
products = Product.objects.filter(shop=request.shop, is_active=True)
```

Sans ce filtre, un commerçant pourrait voir ou modifier les commandes d'un autre — c'est la classe d'attaque la plus courante en multi-tenant. **Toute nouvelle vue doit respecter ce contrat.**

### Variantes de domaine selon l'environnement

Le middleware accepte plusieurs domaines racines pour faciliter le dev :
- Production : `jappesi.sn`
- Dev : `*.localhost`, `*.jayma.local`, `*.jappesi.sn` (si on a configuré `/etc/hosts`)

L'environnement choisit la racine via la variable d'env `JAYMA_ROOT_DOMAIN` (default : `jappesi.sn`).

---

## 4. Settings & configuration

### Découpage des settings

```
config/settings/
├── __init__.py
├── base.py           ← config commune à tous les environnements
├── development.py    ← surcharges dev (DEBUG, mailpit, SMS console…)
└── production.py     ← surcharges prod (HTTPS, HSTS, R2, Sentry…)
```

L'environnement est sélectionné par `DJANGO_SETTINGS_MODULE` :
- Dev : `config.settings.development`
- Prod : `config.settings.production` (forcé dans `docker-compose.prod.yml`)

### Variables d'environnement clés

Voir [`.env.production.example`](../.env.production.example) pour la liste complète. Les plus importantes :

| Variable | Description | Exemple |
|----------|-------------|---------|
| `DJANGO_SECRET_KEY` | Secret signature cookies/CSRF | 50 chars random |
| `DJANGO_DEBUG` | True/False | `False` en prod |
| `DJANGO_ALLOWED_HOSTS` | Hôtes autorisés | `jappesi.sn,.jappesi.sn` |
| `JAYMA_ROOT_DOMAIN` | Domaine racine | `jappesi.sn` |
| `DEFAULT_COMMISSION_RATE` | Taux par défaut (%) | `8.00` |
| `POSTGRES_DB/USER/PASSWORD/HOST/PORT` | BDD | `jayma`/`jayma`/secret/`db`/`5432` |
| `REDIS_URL` | Cache Django | `redis://redis:6379/0` |
| `CELERY_BROKER_URL` | Queue Celery | `redis://redis:6379/1` |
| `EMAIL_HOST/PORT/USE_TLS/HOST_USER/HOST_PASSWORD` | SMTP | SendGrid |
| `DEFAULT_FROM_EMAIL` | From par défaut | `Jappesi <noreply@jappesi.sn>` |
| `USE_R2` | Active stockage Cloudflare R2 | `True` ou `False` |
| `R2_BUCKET_NAME/ACCESS_KEY_ID/SECRET_ACCESS_KEY/ENDPOINT_URL/PUBLIC_URL` | Si `USE_R2=True` | Voir Cloudflare R2 |
| `AT_USERNAME/AT_API_KEY/AT_SENDER_ID` | AfricasTalking | — |
| `WAVE_API_KEY/BUSINESS_ID/WEBHOOK_SECRET` | Wave Business | — |
| `OM_CLIENT_ID/SECRET/MERCHANT_KEY/WEBHOOK_SECRET` | Orange Money | — |
| `CINETPAY_API_KEY/SITE_ID/SECRET_KEY` | CinetPay | — |
| `SENTRY_DSN` | Sentry monitoring | `https://abc@xxx.ingest.sentry.io/123` |

### Stockage fichiers : local vs R2

Le `STORAGES` Django est conditionnel dans [`config/settings/production.py`](../config/settings/production.py) :

```python
if env.bool("USE_R2", default=True):
    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3.S3Storage", "OPTIONS": {...}},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }
# Sinon Django utilise FileSystemStorage par défaut sur /app/media
```

**À retenir** : si `USE_R2=False`, les uploads vont dans le volume Docker `media_data` (servi par nginx via `/media/`). Si `USE_R2=True` mais que les credentials sont placeholder, **les uploads échouent en silence** (SSL handshake fail) → 500 Server Error.

---

## 5. Modèles métier (apps Django)

Vue d'ensemble :

```
accounts        ← User, Auth, OTP
shops           ← Shop, ShopRequest
products        ← Category, Product, ProductImage, Pack, Favorite, StockAlert, Review
cart            ← Cart (session) + AbandonedCart (snapshot relance)
orders          ← Order, OrderItem
payments        ← Payment, WebhookEvent (Wave/OM/CinetPay)
delivery        ← DeliveryZone, Courier
coupons         ← Coupon, CouponUsage
commissions     ← Commission (suivi reversements)
notifications   ← Notification (SMS log)
core            ← Landing, PWA, mentions légales, Tailwind binary
admin_panel     ← Admin Jappesi (approval, modération)
```

### `accounts/`

Authentification multi-rôle, OTP SMS pour les clients.

| Modèle | Champs clés | Notes |
|--------|------------|-------|
| `User` (extends `AbstractUser`) | `role` (`client`/`merchant`/`admin`), `phone` (XOF +221), `phone_verified` (bool), `city` | Properties : `is_merchant`, `is_platform_admin`, `is_client` |
| `ClientAddress` | `user`, `label`, `address`, `city`, `is_default` | Une seule adresse par défaut par user (enforced en `save()`) |
| `OTPToken` | `phone`, `code` (4 chiffres), `created_at`, `expires_at`, `attempts`, `consumed_at` | Code expire en 10 min, max N tentatives |

**Decorators utiles** : `@merchant_required`, `@shop_owner_required` (dans `accounts/decorators.py`).

### `shops/`

Gestion des boutiques (création par admin via `ShopRequest`, paramètres par le commerçant).

| Modèle | Champs clés | Notes |
|--------|------------|-------|
| `Shop` | `owner` (User OneToOne), `slug` (unique), `name`, `logo`, `banner`, `phone`, `email`, `city`, `address`, `is_approved`, `is_active`, `commission_rate` (Decimal %), `theme_color` | Méthode `get_public_url()` → `https://{slug}.{JAYMA_ROOT_DOMAIN}` |
| `ShopRequest` | `full_name`, `email`, `phone`, `city`, `shop_name`, `desired_slug`, `description`, `status` (`pending`/`approved`/`rejected`), `reviewed_by`, `reviewed_at` | Workflow d'inscription |

**Services** : `shops/services/approval.py` — workflow approbation / création de la `Shop` après validation admin.

**Context processors** : `current_shop` (expose `request.shop` dans tous les templates), `jayma_urls` (URL helpers).

### `products/`

Catalogue par boutique : produits simples, packs (composés), variants, images, avis clients, alertes stock.

| Modèle | Champs clés | Notes |
|--------|------------|-------|
| `Category` | `shop`, `name`, `slug`, `position`, `is_active` | Slug unique par shop, auto-incrémenté `-2`, `-3` si collision |
| `Product` | `shop`, `category`, `name`, `slug`, `price` (int XOF), `compare_at_price`, `stock`, `track_stock`, `kind` (`simple`/`pack`), `is_active`, `is_featured` | `unique_together = ("shop", "slug")`. Property `is_available`, `primary_image`, `rating_summary` |
| `PackItem` | `pack`, `item` (Product), `quantity` | Composition d'un pack (uniquement avec products `simple`) |
| `ProductImage` | `product`, `image`, `alt_text`, `is_primary`, `position` | Une image par défaut, ordre custom |
| `Favorite` | `user`, `product` | Liste de favoris par client |
| `StockAlert` | `product`, `client_phone` | "Préviens-moi quand dispo" → SMS quand stock 0→>0 |
| `ProductReview` | `product`, `order`, `client_phone`, `client_name`, `rating` (1-5), `title`, `comment`, `is_approved` | Lié à une commande passée, modération admin/commerçant |

**Signaux** :
- `pre_save` mémorise l'ancien stock
- `post_save` détecte 0 → >0 et lance `notify_stock_back()` Celery task

**Services** : `products/services/stats.py` — stats boutique (top vendus, faible stock, etc.).

### `cart/`

Panier en session (volatil, lié au cookie navigateur) + snapshot pour relance par SMS si abandonné.

| Modèle | Champs clés | Notes |
|--------|------------|-------|
| `AbandonedCart` | `shop`, `client_phone`, `client_name`, `items_json` (list `{product_id, name, unit_price, quantity}`), `total_xof`, `created_at`, `last_seen_at`, `reminded_at`, `recovered_at` | Snapshotté dès qu'on a le téléphone (form checkout, login client) |

**Services** :
- `cart/services/cart.py` — classe `Cart` qui encapsule la session
- `cart/services/abandonment.py` — snapshot vers `AbandonedCart`

**Tasks** : `send_cart_reminders()` — Celery Beat périodique : trouve les `AbandonedCart` inactifs depuis 2-7j non encore relancés, envoie un SMS au client avec le lien du panier.

### `orders/`

Commandes : création (atomique), workflow de statut, livraison, évaluation.

| Modèle | Champs clés | Notes |
|--------|------------|-------|
| `Order` | `shop`, `reference` (8 char hex unique), `client_*` (snapshot), `subtotal/delivery/discount/total_xof`, `coupon_code`, `commission_rate` (snapshot %), `commission_xof`, `merchant_amount_xof`, `status` (`pending`/`confirmed`/`shipped`/`delivered`/`cancelled`/`disputed`), `payment_method`, `payment_status`, `courier`, `delivery_rating`/`comment`, `paid_at`, `delivered_at` | **`commission_rate` figé à la création** |
| `OrderItem` | `order`, `product`, `product_name` (snapshot), `unit_price_xof`, `quantity` | Tous les champs sont snapshotés (pas de FK readable même si product modifié) |

**Services** :
- `orders/services/checkout.py` — `create_order_from_cart()` : transactionnel, snapshots prix, calcul commission, valide coupon, calcule frais livraison
- `orders/services/pricing.py` — `compute_commission(total_xof, rate_percent)` → `(commission_xof, merchant_amount_xof)`
- `orders/services/workflow.py` — transitions de statut autorisées
- `orders/services/clients.py` — commandes filtrées par téléphone client

### `payments/`

Intégration des trois passerelles + webhooks de confirmation.

| Modèle | Champs clés | Notes |
|--------|------------|-------|
| `Payment` | `order`, `provider` (`wave`/`orange_money`/`cinetpay`/`cash`), `status` (`pending`/`success`/`failed`/`cancelled`), `amount_xof`, `provider_reference`, `provider_payload` (JSON brut) | 1-N par order (retries) |
| `WebhookEvent` | `provider`, `event_id` (unique par provider), `payload` (JSON), `signature_valid`, `processed`, `processed_at`, `error` | Idempotence : `unique_together=(provider, event_id)`, `processed` flag |

**Services** :
- `payments/services/providers.py` — dispatcher principal
- `payments/services/wave.py` — `create_checkout_session()`
- `payments/services/orange_money.py` — `create_payment()`
- `payments/services/cinetpay.py` — `create_transaction()`
- Mock automatique si les clés API sont vides → utile en dev

**Tasks** : `notify_merchant_payment_received()` — email + SMS commerçant après paiement confirmé.

### `delivery/`

Zones de livraison tarifées et gestion des livreurs.

| Modèle | Champs clés | Notes |
|--------|------------|-------|
| `DeliveryZone` | `shop`, `name`, `cities` (texte virgule-séparé), `fee_xof`, `position`, `is_active` | Méthode `covers(city_or_area)` → match substring case-insensitive |
| `Courier` | `shop`, `name`, `phone`, `vehicle` (`moto`/`scooter`/`car`/`bike`/`foot`), `covered_zones` (M2M), `notes`, `is_active` | Méthode `whatsapp_link()` → wa.me URL |

**Services** : `delivery/services/zones.py` — `compute_delivery_fee(shop, city_client)` → `(fee_xof, zone)` (calcul live au checkout via HTMX).

### `coupons/`

Codes promo par boutique : pourcentage, montant fixe, livraison offerte.

| Modèle | Champs clés | Notes |
|--------|------------|-------|
| `Coupon` | `shop`, `code` (majuscule, unique par shop), `type` (`percentage`/`fixed`/`freeship`), `value`, `one_per_customer`, `min_order_xof`, `max_uses`, `uses_count`, `valid_from/until`, `is_active` | Méthodes `is_valid_now()`, `compute_discount(subtotal)`, `is_freeship()` |
| `CouponUsage` | `coupon`, `order` (OneToOne), `client_phone`, `discount_xof`, `used_at` | Trace pour `one_per_customer` (un client = un usage max) |

**Services** : `coupons/services/application.py` — `compute_cart_discount(request, shop, subtotal_xof, client_phone)` → `(coupon, discount_xof, freeship_bool)`.

### `commissions/`

Suivi des reversements Jappesi → commerçants.

| Modèle | Champs clés | Notes |
|--------|------------|-------|
| `Commission` | `order` (OneToOne), `shop`, `sale_amount_xof`, `rate` (%), `commission_xof`, `merchant_amount_xof`, `is_paid`, `paid_at`, `payout_reference` | Créée lors de `create_order_from_cart()`. Les vraies sorties bancaires (Wave Business) sont ajoutées plus tard |

### `notifications/`

Logs SMS et email transactionnels (audit trail).

| Modèle | Champs clés | Notes |
|--------|------------|-------|
| `Notification` | `type`, `phone`, `message`, `status`, `sent_at` | Pour l'audit, retry, debug |

**Services** : `notifications/services/sms.py` — dispatcher de backend SMS (`AfricasTalkingSMSBackend` en prod, `ConsoleSMSBackend` en dev qui logge sans envoyer).

### `core/`

Landing page, mentions légales, PWA (manifest + service worker), gestion du binaire Tailwind.

**Tasks** :
- `notify_admin_of_new_request()` — email à l'admin quand une `ShopRequest` est créée
- `send_merchant_welcome()` — email + SMS de bienvenue après approbation

### `admin_panel/`

Panneau d'administration Jappesi, accessible uniquement sur `admin.jappesi.sn` aux users `is_platform_admin=True`.

Fonctionnalités :
- Approbation / rejet des `ShopRequest`
- Statistiques globales (CA, commissions, top boutiques)
- Modération des avis produits
- Logs des webhooks paiements
- Audit log (qui a fait quoi sur la plateforme)

L'interface Django admin de fallback reste accessible sur `/django/` (sécurisée par le décorateur superuser).

---

## 6. URLs & routing

| URLconf | Sous-domaine | Routes principales |
|---------|--------------|-------------------|
| `config.urls_public` | `jappesi.sn` | `/`, `/comptes/login`, `/comptes/inscription`, `/inscription-boutique/`, `/mentions-legales/`, `/cgu/`, `/cgv/`, `/confidentialite/` |
| `config.urls_dashboard` | `dashboard.jappesi.sn` | `/`, `/produits/`, `/categories/`, `/commandes/`, `/clients/`, `/livreurs/`, `/zones-livraison/`, `/promos/`, `/revenus/`, `/parametres/` |
| `config.urls_admin` | `admin.jappesi.sn` | `/`, `/django/` (Django admin), `/demandes/`, `/boutiques/`, `/audit/` |
| `config.urls_shop` | `<slug>.jappesi.sn` | `/`, `/produits/`, `/produit/<slug>/`, `/panier/`, `/commander/`, `/paiement/<provider>/`, `/suivi/<ref>/`, `/api/frais-livraison/` (HTMX) |

Pour la liste exhaustive : `config/urls_*.py`.

---

## 7. Workflows métier

### Inscription commerçant

```
1. Visiteur sur jappesi.sn → /inscription-boutique/
2. Soumet formulaire → ShopRequest créée (status=pending)
3. Celery task notify_admin_of_new_request() → email à l'admin
4. Admin se connecte sur admin.jappesi.sn → liste demandes
5. Admin approuve OU rejette
   - Si approuvée :
     a. User créé avec role=merchant + mot de passe temporaire
     b. Shop créée (is_approved=True, is_active=True)
     c. Celery task send_merchant_welcome() → email + SMS au commerçant
   - Si rejetée :
     a. ShopRequest.status = rejected
     b. Email de refus au demandeur
6. Commerçant se connecte sur dashboard.jappesi.sn avec credentials reçus
```

### Cycle de vie produit

```
1. Commerçant crée Category sur le dashboard
2. Crée Product (simple ou pack)
   - Slug auto = slugify(name), unique par shop (suffixe -2, -3 si collision)
   - Pour pack : track_stock=False forcé, ajoute PackItems (children = simple products)
3. Ajoute ProductImage(s) — au moins une, première = primary par défaut
4. Configure stock + track_stock flag (toggle "ne pas suivre le stock")
5. Produit visible sur <slug>.jappesi.sn/produit/<slug>/
6. Si produit épuisé, clients peuvent demander StockAlert via SMS
7. Quand commerçant remet en stock (0 → >0), signal Django déclenche
   notify_stock_back() Celery task → SMS aux alertants
```

### Commande complète

```
1. Client navigue sur boutique.jappesi.sn/produits/
2. Ajoute produits au panier (session)
3. Si client se connecte ou entre son téléphone, AbandonedCart snapshotté
4. Click "Commander" → /commander/
   - Form : nom, phone, adresse, ville, notes
   - Calcul frais livraison live (HTMX) selon ville saisie
5. Soumet form → create_order_from_cart() :
   - Crée Order avec snapshot prix unitaires + commission_rate actuel
   - Crée OrderItems
   - Valide Coupon (date, montant min, quotas)
   - Crée Commission record
   - Vide le panier session
   - Marque AbandonedCart.recovered_at
6. Redirect vers initiate_payment(provider=Wave|OM|CinetPay)
7. Provider redirect → user paie → return URL
8. Webhook provider → /paiements/webhook/{provider}/
   - WebhookEvent enregistré (idempotence)
   - Vérification signature
   - Payment.status = success
   - Order.payment_status = paid, status = confirmed, paid_at = now
9. Celery task notify_merchant_payment_received() :
   - Email + SMS commerçant
10. Commerçant traite la commande dans le dashboard :
    - Assigne courier
    - Status → shipped
11. Livraison effectuée → Status = delivered, delivered_at = now
12. Client peut noter la livraison (1-5 étoiles)
13. Commission devient éligible au reversement
```

### Relance panier abandonné

```
1. AbandonedCart créée à l'étape 3 ci-dessus
2. Tous les X minutes, Celery Beat exécute send_cart_reminders()
3. Sélectionne AbandonedCarts où :
   - last_seen_at entre 2h et 7j dans le passé
   - reminded_at IS NULL
   - recovered_at IS NULL
4. Pour chaque : envoie SMS "Termine ta commande : {shop_url}/panier/"
5. Marque reminded_at = now (jamais relancé deux fois)
```

### Gestion des reversements (manuel pour l'instant)

```
1. Admin Jappesi consulte commissions/ avec is_paid=False sur le dashboard admin
2. Effectue les virements Wave Business → commerçants
3. Marque is_paid=True + paid_at + payout_reference dans le dashboard
4. Commerçant voit le solde reversé sur son dashboard /revenus/
```

> 💡 **À automatiser plus tard** : le reversement automatique via API Wave Business → ratio risque / valeur ajoutée à évaluer.

---

## 8. Tâches asynchrones (Celery)

### Liste des tâches

| Tâche | Trigger | Description |
|-------|---------|-------------|
| `notify_admin_of_new_request(request_id)` | Signal `post_save` sur `ShopRequest` | Email admin |
| `send_merchant_welcome(shop_id, temp_password)` | Approbation manuelle | Email + SMS commerçant |
| `send_cart_reminders()` | **Beat schedule** (à confirmer) | Boucle sur `AbandonedCart`, envoie SMS |
| `notify_stock_back(product_id)` | Signal `post_save` sur `Product` (stock 0→>0) | SMS aux `StockAlert` du produit |
| `notify_merchant_payment_received(order_id)` | Webhook paiement success | Email + SMS au commerçant |

### Beat schedule

Le scheduler `django_celery_beat.schedulers:DatabaseScheduler` est utilisé : les tâches récurrentes sont définies en BDD via l'admin Django, pas en code. Cela permet à un admin de modifier la fréquence sans déployer.

> ⚠️ **Action à faire après le déploiement initial** : ouvrir l'admin Django (sur `admin.jappesi.sn/django/`) et configurer manuellement la `PeriodicTask` pour `send_cart_reminders` (interval recommandé : toutes les 2 heures).

### Lancer un worker en local

```bash
docker compose exec web celery -A config worker -l info
docker compose exec web celery -A config beat -l info
```

(Déjà gérés par les containers `celery_worker` et `celery_beat` du compose dev.)

---

## 9. Frontend

### Templates

106 fichiers `.html` dans `templates/`, organisés par domaine :

```
templates/
├── base.html               ← layout partagé
├── accounts/               ← login, signup, password-reset
├── admin_panel/            ← admin Jappesi
├── cart/                   ← panier, ajout produit
├── client/                 ← profil client, adresses, commandes
├── core/                   ← landing, mentions, CGU
├── coupons/                ← formulaire promo dashboard
├── dashboard/              ← layout merchant
├── delivery/               ← zones, livreurs
├── orders/                 ← liste commandes, détail, suivi
├── partials/               ← fragments HTMX réutilisables
├── payments/               ← écrans confirmation, retour
├── products/               ← catalogue, fiche, formulaire
├── public/                 ← landing publique boutique
└── shops/                  ← settings boutique
```

### Tailwind v4

Tailwind est intégré via le **binaire CLI standalone** (pas via npm). Il est téléchargé automatiquement par `core/management/commands/install_tailwind.py`.

- Source : [`static/src/main.css`](../static/src/main.css)
- Output : `static/css/main.css` (généré, ne pas commit)
- Build : `make css` (ou `tailwindcss -i ... -o ...` direct)
- Watch (dev) : `make css-watch`

**Couleurs custom** (palette sénégalaise chaleureuse) : variables CSS `--color-jayma-50` à `--color-jayma-900` (orange brique, marron, ocre).

> Note : le préfixe est encore `jayma-` (legacy avant le rebrand). À renommer en `jappesi-` plus tard.

### HTMX

Utilisé pour :
- Validation form en live (slug disponibilité, prix calcul)
- Recalcul frais livraison quand on change la ville
- Ajout/suppression panier sans reload
- Notifications poll (cf logs : `GET /notifications/?since=...`)

Pas de framework JS (pas de React, Vue, etc.) — Django + Tailwind + HTMX = stack légère, performante, low-JS.

### Service Worker / PWA

Un fichier `sw.js` est servi (cf logs : `GET /sw.js HTTP/1.0 200`). Le manifest PWA est exposé pour permettre l'installation sur mobile (icône sur l'écran d'accueil). Contenu du SW non audité dans cette doc — probablement basique (cache statique).

---

## 10. Sécurité

### Middleware

Ordre dans [`config/settings/base.py`](../config/settings/base.py) :

```
1. SecurityMiddleware
2. WhiteNoiseMiddleware
3. SessionMiddleware
4. CommonMiddleware
5. CsrfViewMiddleware
6. AuthenticationMiddleware
7. MessageMiddleware
8. XFrameOptionsMiddleware
9. HtmxMiddleware
10. TenantMiddleware  ← custom Jappesi
```

### Isolation tenant

Cf [section 3](#3-architecture-multi-tenant). **Toute vue dashboard ou shop** doit filtrer ses querysets par `request.shop` (ou `request.user.shop` côté dashboard). Sans ça, un commerçant peut accéder aux données d'un autre.

### CSRF

- Dev : `CSRF_TRUSTED_ORIGINS` accepte `*.jayma.local`, `*.localhost`, `127.0.0.1`
- Prod : `SECURE_SSL_REDIRECT=True`, `CSRF_COOKIE_SECURE=True`, `SESSION_COOKIE_SECURE=True`

### HTTPS / HSTS (prod uniquement)

```python
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365  # 1 an
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
```

### Webhooks

Chaque webhook paiement :
1. Stocke le payload brut dans `WebhookEvent`
2. Vérifie la signature (HMAC du provider) — si invalide, `signature_valid=False` et on n'agit pas
3. Vérifie l'idempotence via `event_id` (`unique_together=("provider", "event_id")`)
4. Si valide & non encore traité, marque `processed=True` puis met à jour `Payment` et `Order`

Cela protège contre :
- Replay attacks (idempotence)
- Spoofing (signature)
- Retraitement (flag `processed`)

### Sentry & PII

Sentry envoie les exceptions avec stacktrace + variables locales **mais pas** : email, IP, identifiants utilisateur (`send_default_pii=False`). RGPD-compliant par défaut. À activer manuellement si besoin de debug fin.

### Rate limiting

⚠️ **Pas de rate limiting actif sur les endpoints publics** (login, signup, webhooks). À ajouter (django-ratelimit ou nginx limit_req) avant scaling sérieux.

---

## 11. Développement local

### Prérequis

- Docker + docker compose
- Make (Linux/Mac, ou WSL Windows)
- (Optionnel) `dnsmasq` ou modif `/etc/hosts` pour les sous-domaines locaux

### Setup `/etc/hosts`

```bash
sudo tee -a /etc/hosts <<EOF
127.0.0.1   jayma.local
127.0.0.1   admin.jayma.local
127.0.0.1   dashboard.jayma.local
127.0.0.1   demo.jayma.local
EOF
```

### Lancer la stack dev

```bash
git clone git@github.com:alassanaynwa-dot/jayma.git
cd jayma
cp .env.example .env
# (Renseigner les valeurs si besoin — par défaut tout marche en dev)

docker compose up -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

Accès :
- Web : http://jayma.local:8002
- Admin : http://admin.jayma.local:8002
- Dashboard : http://dashboard.jayma.local:8002
- Mailpit (capture emails) : http://localhost:8025
- Postgres exposé : `localhost:5434`
- Redis exposé : `localhost:6381`

### Commandes courantes

```bash
make help                    # liste les commandes Makefile
make migrate                 # docker compose exec web python manage.py migrate
make shell                   # Django shell
make css                     # build Tailwind (one-shot, minify)
make css-watch               # build Tailwind en watch (dev)
make test                    # docker compose exec web pytest
docker compose logs -f web   # logs en live
```

### Tests

- Configuration : [`pytest.ini`](../pytest.ini) — utilise `config.settings.development`
- Fixtures globales : [`conftest.py`](../conftest.py) — `merchant_user`, `shop`, `category`, `product`, `pack`, `zone_dakar`, `courier`, `coupon_10pct`, `coupon_freeship`
- Markers :
  - Aucun marker → tests rapides (unit)
  - `@pytest.mark.integration` → tests plus lents

```bash
pytest                       # tous les tests
pytest -m "not integration"  # rapides seulement
pytest products/             # une app
pytest -k "slug"             # filtre par nom
```

---

## 12. Production

### Référence rapide

- **Setup VPS de zéro** → [`deploy/VPS_SETUP.md`](../deploy/VPS_SETUP.md) (10 phases ordonnées)
- **Runbook ops courantes** → [`deploy/README.md`](../deploy/README.md)
- **Fiche services tiers** → [`deploy/SERVICES.md`](../deploy/SERVICES.md)

### Déploiement d'une mise à jour

```bash
ssh jappesi@213.136.64.42
cd /opt/jappesi
./deploy/deploy.sh
```

Le script :
1. `git pull --ff-only`
2. Rebuild image `web` + `celery_*`
3. Migrations
4. Build Tailwind
5. `collectstatic --ignore=src` (le source Tailwind n'est pas collecté)
6. Restart services applicatifs (rolling)
7. Restart nginx (refresh DNS du nouvel upstream)
8. Vérification santé via `docker compose ps`

### Backup automatique

```
0 3 * * * /opt/jappesi/deploy/backup.sh >> /var/log/jappesi-backup.log 2>&1
```

Garde 14 jours de dumps gzippés dans `deploy/backups/`. Pour copier hors VPS (DR), ajouter un `rsync` ou un push vers R2/S3.

### Rollback

```bash
cd /var/www/html/jayma   # depuis la machine locale
git revert HEAD
git push origin main

# Sur le VPS
ssh jappesi@213.136.64.42
cd /opt/jappesi
./deploy/deploy.sh
```

### Monitoring

- **Sentry** (`https://sentry.io`) : erreurs Django + Celery, alerte mail à chaque nouvelle issue
- **Logs nginx + gunicorn** : `docker compose logs -f web nginx`
- **Health Postgres / Redis** : `docker compose ps` → status `(healthy)`

---

## 13. Dette technique & TODO

Recensé pendant l'audit. Aucun n'est bloquant pour la prod, mais à traiter au fil de l'eau.

### ✅ Réglés (sprint 1)

| # | Sujet | Commit |
|---|-------|--------|
| 1 | Préfixe couleurs Tailwind renommé `jayma-` → `jappesi-` (62 fichiers, 166 occ.) | sprint 1 |
| 2 | `USE_R2` défaut aligné à `False` dans `production.py` (cohérent avec `base.py`) | `2c8a36e` |
| 3 | Beat schedule défini via management command (cf #10) | `2c8a36e` |
| 10 | Management command `setup_periodic_tasks` créée + appelée par `deploy.sh` | `2c8a36e` |
| 17 | Endpoint `/healthz/` qui teste DB + cache Redis | `2c8a36e` |

### À faire (sprints suivants)

| # | Sujet | Fichier | Action proposée |
|---|-------|---------|-----------------|
| 4 | OTP en BDD plutôt que Redis | `accounts/models.py` | Acceptable (audit trail), mais Redis serait plus performant. À évaluer plus tard |
| 5 | Templates email en f-string Python | tasks Celery | Migrer vers templates Django (`render_to_string`) pour HTML pro |
| 6 | Pas de rate limiting | partout | Ajouter `django-ratelimit` sur login, signup, webhooks (au moins) |
| 7 | Webhooks paiement : pas de retry serveur | `payments/views.py` | Si HTTP 500 sur réception, certains providers retry — vérifier qu'on est idempotent (déjà ok) |
| 8 | Status order `disputed` mais pas de vue | `orders/` | Soit retirer le status, soit créer le workflow |
| 9 | Multi-currency hardcodé XOF | partout | Documenter la limite, prévoir abstraction si extension Afrique de l'Ouest |
| 11 | Reversement commissions manuel | `commissions/` | API Wave Business pour automatisation |
| 12 | Slug auto sur `Product` et `Category` (ok), mais pas sur `Shop` | `shops/models.py` | À vérifier : faut-il pareil ? Probablement non (admin saisit explicitement) |
| 13 | Email transactionnel souvent en spam Gmail | infra | Long terme : Search Console + DMARC `p=quarantine` après 3 mois de bons envois |
| 14 | Tests : couverture inconnue | partout | Ajouter `pytest --cov` au CI quand on aura un CI |
| 15 | Pas de CI configuré (GitHub Actions, etc.) | racine | Ajouter `.github/workflows/test.yml` (lint + tests sur PR) |
| 16 | `requirements.txt` sans pinning strict | `requirements.txt` | Migrer vers `pip-compile` ou `uv` lock pour reproductibilité |

---

## 14. Lexique

| Terme | Définition |
|-------|------------|
| **Tenant** | Une boutique cliente sur Jappesi (un commerçant). Identifié par son `slug` |
| **Multi-tenant** | Architecture où une seule application sert plusieurs clients isolés |
| **Sous-domaine** | Une URL comme `boutique.jappesi.sn` (vs `jappesi.sn`) |
| **Slug** | Identifiant URL-safe d'une boutique ou produit (ex: `boubou-brode`) |
| **XOF** | Code ISO du Franc CFA (Afrique de l'Ouest), monnaie sénégalaise — pas de subdivision |
| **OTP** | One-Time Password — code à usage unique envoyé par SMS pour valider un téléphone |
| **HTMX** | Bibliothèque qui permet d'envoyer des fragments HTML depuis le serveur sur action user, sans framework JS |
| **PWA** | Progressive Web App — site web installable comme une app mobile |
| **R2** | Service de stockage Cloudflare, S3-compatible, sans frais de bande passante sortante |
| **Webhook** | Endpoint HTTP appelé par un service tiers pour notifier un événement (ex : paiement confirmé) |
| **Idempotence** | Propriété d'une opération qui peut être répétée sans changer le résultat (essentielle pour les webhooks) |
| **Commission** | Pourcentage prélevé par Jappesi sur chaque vente (default 8 %) |
| **Reversement** | Virement Jappesi → commerçant des sommes encaissées moins commission |
| **Beat** | Le scheduler Celery (`celery_beat`) qui lance les tâches périodiques |
| **TenantMiddleware** | Le composant qui dispatche les requêtes selon le sous-domaine |

---

*Dernière mise à jour : 2026-04-29 — basé sur le code à `eb072e5` + commits ultérieurs (Sentry, fix slug, deploy.sh, backup.sh).*
