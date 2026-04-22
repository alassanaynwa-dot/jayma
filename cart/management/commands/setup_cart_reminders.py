"""
Crée/met à jour la tâche planifiée django-celery-beat qui envoie les
rappels de paniers abandonnés toutes les 30 minutes.

Usage :
    python manage.py setup_cart_reminders
"""
from django.core.management.base import BaseCommand
from django_celery_beat.models import IntervalSchedule, PeriodicTask


class Command(BaseCommand):
    help = "Configure la tâche planifiée de relance des paniers abandonnés."

    def handle(self, *args, **options):
        schedule, _ = IntervalSchedule.objects.get_or_create(
            every=30, period=IntervalSchedule.MINUTES,
        )
        task, created = PeriodicTask.objects.update_or_create(
            name="Relance paniers abandonnés",
            defaults={
                "interval": schedule,
                "task": "cart.tasks.send_cart_reminders",
                "enabled": True,
            },
        )
        verb = "créée" if created else "mise à jour"
        self.stdout.write(self.style.SUCCESS(
            f"✓ Tâche « {task.name} » {verb} — déclenchement toutes les 30 min"
        ))
