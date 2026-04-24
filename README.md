# Jappesi.sn

Plateforme SaaS e-commerce multi-tenant pour commerçants sénégalais.
Chaque commerçant obtient sa boutique sur `<slug>.jappesi.sn`.
Modèle : commission de 8% sur les ventes, pas d'abonnement.

## Stack

- Django 5.2 LTS + django-unfold
- HTMX + Alpine.js + Tailwind CSS (pas de SPA)
- PostgreSQL 16 + Redis 7 + Celery
- Docker Compose pour le dev

## Démarrage rapide (Docker)

```bash
cp .env.example .env          # puis remplir les vraies valeurs
make up                       # démarre tous les services
make migrate                  # applique les migrations
make createsuperuser          # crée un admin
```

Services exposés sur la machine hôte :

| Service     | URL                       |
|-------------|---------------------------|
| Django      | http://localhost:8002     |
| Nginx       | http://localhost:8090     |
| Mailpit UI  | http://localhost:8026     |
| PostgreSQL  | localhost:5434            |
| Redis       | localhost:6381            |

## Tester les sous-domaines en local

**Pas besoin de `/etc/hosts`** : les navigateurs résolvent nativement `*.localhost` sur 127.0.0.1.

| Tenant | URL locale |
|---|---|
| Landing publique | http://localhost:8002/ |
| Dashboard commerçant | http://dashboard.localhost:8002/ |
| Admin plateforme | http://admin.localhost:8002/ |
| Boutique publique `<slug>` | http://`<slug>`.localhost:8002/ (ex : http://demo.localhost:8002/) |

Testé sur Chrome, Firefox, Safari, Edge — aucune config système requise.

## Arborescence

```
config/          Projet Django (settings, urls, middleware tenant)
core/            Landing jappesi.sn, formulaire demande boutique
accounts/        User custom (client/commerçant/admin), auth
shops/           Shop, ShopRequest, context_processor tenant
products/        Category, Product, ProductImage
cart/            Panier session-based (pas en DB)
orders/          Order, OrderItem, pricing service
payments/        Wave + Orange Money + CinetPay + webhooks
commissions/     Suivi commissions et reversements
notifications/   SMS (AfricasTalking) + Email
```

## Commandes utiles

```bash
make help         # liste toutes les commandes Make
make logs         # logs Django
make shell        # shell Django
make test         # lancer les tests
```

## Principes

1. Prix en XOF entiers — jamais de décimales
2. Mobile-first absolu (cible 375px)
3. Logique métier dans `services.py` uniquement
4. Commentaires en français
5. Une feature = une branche Git
