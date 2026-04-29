"""Crée / met à jour les tâches périodiques Celery Beat en BDD.

À appeler après chaque déploiement (idempotent). Sans cela, les tâches comme
``send_cart_reminders`` ne tournent pas en prod, même si Celery Beat est lancé.

Usage:
    python manage.py setup_periodic_tasks
"""
from django.core.management.base import BaseCommand
from django_celery_beat.models import IntervalSchedule, PeriodicTask


# (name, task, every, period, description)
PERIODIC_TASKS = [
    (
        "cart-abandoned-reminders",
        "cart.tasks.send_cart_reminders",
        2,
        IntervalSchedule.HOURS,
        "Envoie un SMS aux clients dont le panier est abandonné entre 2h et 7j.",
    ),
]


class Command(BaseCommand):
    help = "Crée / met à jour les PeriodicTask Celery Beat en BDD (idempotent)."

    def handle(self, *args, **options):
        for name, task_path, every, period, description in PERIODIC_TASKS:
            schedule, _ = IntervalSchedule.objects.get_or_create(
                every=every, period=period,
            )
            obj, created = PeriodicTask.objects.update_or_create(
                name=name,
                defaults={
                    "task": task_path,
                    "interval": schedule,
                    "description": description,
                    "enabled": True,
                },
            )
            verb = "créée" if created else "mise à jour"
            self.stdout.write(self.style.SUCCESS(
                f"PeriodicTask '{name}' {verb} → {task_path} (toutes les {every} {period}).",
            ))
