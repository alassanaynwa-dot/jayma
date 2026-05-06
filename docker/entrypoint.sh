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

# Si le binaire Tailwind manque (téléchargement échoué pendant le build à
# cause d'une connexion lente), on retente ici. Au pire, on continue
# sans bloquer le démarrage de Django.
if [ ! -x /usr/local/bin/tailwindcss ]; then
    echo ">>> Tailwind binaire absent, téléchargement..."
    curl --retry 5 --retry-delay 10 --connect-timeout 60 --max-time 300 \
        -sL -o /usr/local/bin/tailwindcss \
        "https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64" \
        && chmod +x /usr/local/bin/tailwindcss \
        && echo ">>> Tailwind binaire téléchargé." \
        || echo ">>> WARN: échec téléchargement Tailwind, la CSS ne sera pas rebuildée."
fi

# Builder la CSS Tailwind si absente (permet au container de démarrer sur clone frais)
if [ -f "/app/static/src/main.css" ] && [ ! -f "/app/static/css/main.css" ] && [ -x /usr/local/bin/tailwindcss ]; then
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
