from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import NotificationLog


@admin.register(NotificationLog)
class NotificationLogAdmin(ModelAdmin):
    list_display = ("channel", "recipient", "status", "created_at", "sent_at")
    list_filter = ("channel", "status")
    search_fields = ("recipient", "subject")
    readonly_fields = ("created_at", "sent_at", "provider_response")
