"""Configuration Celery pour Jayma."""
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("jayma")

# Charger la config depuis les settings Django (prefix CELERY_)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-découverte des tasks dans chaque app
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    """Tâche de debug, vérifie que Celery tourne."""
    print(f"Request: {self.request!r}")
