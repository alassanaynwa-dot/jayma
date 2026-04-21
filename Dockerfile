# Image Python 3.12 slim pour légèreté
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

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

# Binaire Tailwind CSS CLI standalone (pas besoin de Node.js)
ARG TAILWIND_URL=https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64
RUN curl -sL -o /usr/local/bin/tailwindcss "$TAILWIND_URL" && \
    chmod +x /usr/local/bin/tailwindcss

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
