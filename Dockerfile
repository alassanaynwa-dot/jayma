# Image Python 3.12 slim pour légèreté
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
# Connexions lentes : timeout généreux + plusieurs retries
ENV PIP_DEFAULT_TIMEOUT=120
ENV PIP_RETRIES=5

WORKDIR /app

# Dépendances système (Pillow, psycopg, outils réseau)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libjpeg-dev \
        zlib1g-dev \
        gettext \
        curl \
        ca-certificates \
        netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Binaire Tailwind CSS CLI standalone (pas besoin de Node.js).
# Tolérant aux connexions lentes : retry 5x + timeout 60s/connexion.
# Si le download échoue (réseau capricieux), on continue : l'entrypoint
# tentera à nouveau au boot du container et on n'a perdu que la CSS
# pré-buildée — le code Python est complet et exécutable.
ARG TAILWIND_URL=https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64
RUN curl --retry 5 --retry-delay 10 --connect-timeout 60 --max-time 300 \
        -sL -o /usr/local/bin/tailwindcss "$TAILWIND_URL" \
    && chmod +x /usr/local/bin/tailwindcss \
    || echo "WARN: Tailwind binaire pas téléchargé pendant le build — l'entrypoint le téléchargera au boot."

# Installer les dépendances Python en premier (cache Docker)
COPY requirements.txt requirements-dev.txt /app/
RUN pip install -r requirements-dev.txt

# Copier le code
COPY . /app/

# Script d'entrée (attend PostgreSQL, build CSS, applique migrations)
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
