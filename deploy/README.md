# Déploiement Jayma — runbook

## Prérequis VPS (Ubuntu 22.04/24.04)

```bash
apt update && apt upgrade -y
apt install -y docker.io docker-compose-v2 git certbot ufw
systemctl enable --now docker
ufw allow 22,80,443/tcp && ufw enable
```

## 1. Cloner le repo

```bash
mkdir -p /opt && cd /opt
git clone <repo-url> jayma
cd jayma
cp .env.production.example .env.production
nano .env.production   # renseigner tous les secrets
```

## 2. Obtenir le certificat wildcard (une fois)

Let's Encrypt wildcard exige un challenge DNS (impossible en HTTP-01). Utilise certbot avec le plugin DNS de ton registrar (Cloudflare recommandé) :

```bash
# Installer le plugin (Cloudflare exemple)
apt install -y python3-certbot-dns-cloudflare

# Créer /root/.secrets/cloudflare.ini :
#   dns_cloudflare_api_token = <ton token d'API scope DNS:Edit sur djayma.sn>
chmod 600 /root/.secrets/cloudflare.ini

certbot certonly \
    --dns-cloudflare \
    --dns-cloudflare-credentials /root/.secrets/cloudflare.ini \
    -d djayma.sn -d '*.djayma.sn' \
    --agree-tos -m contact@djayma.sn --non-interactive
```

Le renouvellement auto est géré par le service `certbot` dans docker-compose.prod.yml (renew toutes les 12h).

## 3. Premier lancement

```bash
./deploy/deploy.sh
```

Ce script :
1. Pull les sources
2. Build les images web + celery
3. Applique les migrations
4. Collect les statics + compile Tailwind
5. Start tous les services

## 4. Créer le premier superuser admin

```bash
docker compose -f deploy/docker-compose.prod.yml --env-file .env.production \
    run --rm web python manage.py createsuperuser
```

## 5. Backups automatiques

Ajouter au crontab (`crontab -e`) :

```
0 3 * * * /opt/jayma/deploy/backup.sh >> /var/log/jayma-backup.log 2>&1
```

Conserve 14 jours de dumps dans `deploy/backups/`.

## 6. Déploiement de mises à jour

```bash
cd /opt/jayma
./deploy/deploy.sh
```

Rolling restart sans downtime perçu (nginx reste up).

## Debug / Ops

```bash
# Logs
docker compose -f deploy/docker-compose.prod.yml logs -f web

# Shell Django
docker compose -f deploy/docker-compose.prod.yml run --rm web python manage.py shell

# Status
docker compose -f deploy/docker-compose.prod.yml ps

# Rollback (1 commit)
git revert HEAD && ./deploy/deploy.sh
```

## Optimisation image (optionnel)

Le `Dockerfile` utilisé est celui du dev — il installe `requirements-dev.txt`
(inclut debug toolbar, etc.). Pour une image prod plus légère, modifier la
ligne dans `Dockerfile` :

```dockerfile
RUN pip install -r requirements.txt   # à la place de requirements-dev.txt
```

Ou créer un `Dockerfile.prod` dédié et référencer `dockerfile: Dockerfile.prod`
dans `deploy/docker-compose.prod.yml`.

## Sécurité — checklist

- [ ] `DJANGO_SECRET_KEY` unique (généré — `python -c 'import secrets; print(secrets.token_urlsafe(50))'`)
- [ ] `DJANGO_DEBUG=False` (imposé par `production.py`, vérifie quand même)
- [ ] `POSTGRES_PASSWORD` fort (32+ chars)
- [ ] Port 5432 et 6379 **non exposés** (seulement internes) → vérifié dans compose
- [ ] UFW bloque tout sauf 22, 80, 443
- [ ] SSH key-only (pas de password login)
- [ ] Sentry DSN renseigné → alertes erreurs actives
- [ ] Webhooks Wave/OM/CinetPay ont une **signature secrète** côté provider et ton endpoint vérifie
