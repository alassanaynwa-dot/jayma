#!/bin/bash
# ============================================================
# JAYMA — script de déploiement production
# Lance depuis le serveur : cd /opt/jayma && ./deploy/deploy.sh
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

COMPOSE="docker compose -f deploy/docker-compose.prod.yml --env-file .env.production"

echo ">>> 1. Pull des dernières sources"
git pull --ff-only

echo ">>> 2. Rebuild image web (+ celery) avec le nouveau code"
$COMPOSE build web celery_worker celery_beat

echo ">>> 3. Application des migrations"
$COMPOSE run --rm web python manage.py migrate --noinput

echo ">>> 4. Collecte des fichiers statiques"
$COMPOSE run --rm web python manage.py collectstatic --noinput

echo ">>> 5. Build de Tailwind CSS"
$COMPOSE run --rm web tailwindcss -i /app/static/src/main.css -o /app/static_collected/css/main.css --minify

echo ">>> 6. Restart des services (rolling)"
$COMPOSE up -d --no-deps --remove-orphans web celery_worker celery_beat nginx

echo ">>> 7. Vérification santé"
sleep 5
$COMPOSE ps

echo ">>> ✓ Déploiement terminé."
