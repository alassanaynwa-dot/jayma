"""Log des notifications envoyées (SMS / Email)."""
from django.db import models


class NotificationLog(models.Model):
    class Channel(models.TextChoices):
        SMS = "sms", "SMS"
        EMAIL = "email", "Email"

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        SENT = "sent", "Envoyé"
        FAILED = "failed", "Échoué"

    channel = models.CharField(max_length=10, choices=Channel.choices)
    recipient = models.CharField(max_length=200, help_text="Numéro ou email.")
    subject = models.CharField(max_length=200, blank=True)
    body = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    provider_response = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.get_channel_display()} → {self.recipient}"
