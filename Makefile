.PHONY: help up down logs build migrate makemigrations shell createsuperuser test clean collectstatic worker beat css css-watch install-tailwind

help:  ## Afficher cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ================ Tailwind ================

install-tailwind:  ## Télécharger le binaire Tailwind CLI (une fois)
	./scripts/install_tailwind.sh

css:  ## Builder la feuille de style Tailwind minifiée
	./.bin/tailwindcss -i static/src/main.css -o static/css/main.css --minify

css-watch:  ## Builder en watch (dev) — rebuilds à chaque sauvegarde
	./.bin/tailwindcss -i static/src/main.css -o static/css/main.css --watch

# ================ Docker ================

up:  ## Démarrer tous les services Docker
	docker compose up -d
	@echo ""
	@echo "Django        : http://localhost:8002"
	@echo "Mailpit UI    : http://localhost:8026"
	@echo "PostgreSQL    : localhost:5434"
	@echo "Redis         : localhost:6381"

down:  ## Arrêter tous les services
	docker compose down

logs:  ## Afficher les logs Django
	docker compose logs -f web

logs-all:  ## Afficher les logs de tous les services
	docker compose logs -f

build:  ## Rebuilder les images Docker
	docker compose build

ps:  ## État des services
	docker compose ps

# ================ Django ================

migrate:  ## Appliquer les migrations
	docker compose exec web python manage.py migrate

makemigrations:  ## Créer les migrations
	docker compose exec web python manage.py makemigrations

shell:  ## Ouvrir un shell Django
	docker compose exec web python manage.py shell_plus || docker compose exec web python manage.py shell

bash:  ## Ouvrir un bash dans le container web
	docker compose exec web bash

createsuperuser:  ## Créer un superuser
	docker compose exec web python manage.py createsuperuser

collectstatic:  ## Collecter les fichiers statiques
	docker compose exec web python manage.py collectstatic --noinput

# ================ Celery ================

worker:  ## Logs worker Celery
	docker compose logs -f celery_worker

beat:  ## Logs Celery beat
	docker compose logs -f celery_beat

# ================ Tests & qualité ================

test:  ## Lancer les tests
	docker compose exec web pytest

lint:  ## Lancer ruff
	docker compose exec web ruff check .

format:  ## Formater le code
	docker compose exec web black .
	docker compose exec web ruff check --fix .

# ================ Nettoyage ================

clean:  ## Supprimer les fichiers compilés Python
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

reset-db:  ## ATTENTION : supprimer la DB et recréer
	docker compose down -v
	docker compose up -d db redis
	sleep 3
	docker compose up -d web
	sleep 3
	$(MAKE) migrate
