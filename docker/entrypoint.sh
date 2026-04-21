#!/bin/bash
set -e

# Attendre que PostgreSQL soit prêt
if [ -n "${POSTGRES_HOST:-}" ]; then
    echo ">>> Attente de PostgreSQL sur $POSTGRES_HOST:${POSTGRES_PORT:-5432}..."
    until nc -z "$POSTGRES_HOST" "${POSTGRES_PORT:-5432}"; do
        sleep 0.5
    done
    echo ">>> PostgreSQL est prêt."
fi

# Builder la CSS Tailwind si absente (permet au container de démarrer sur clone frais)
if [ -f "/app/static/src/main.css" ] && [ ! -f "/app/static/css/main.css" ]; then
    echo ">>> Build initial de Tailwind CSS..."
    mkdir -p /app/static/css
    tailwindcss -i /app/static/src/main.css -o /app/static/css/main.css --minify || true
fi

# Appliquer les migrations automatiquement en dev
if [ "${DJANGO_DEBUG:-}" = "True" ]; then
    echo ">>> Application des migrations..."
    python manage.py migrate --noinput || echo ">>> Migrations différées (normal au 1er run)."
fi

echo ">>> Démarrage : $@"
exec "$@"
