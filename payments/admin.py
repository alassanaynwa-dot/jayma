from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Payment, WebhookEvent


@admin.register(Payment)
class PaymentAdmin(ModelAdmin):
    list_display = ("order", "provider", "status", "amount_xof", "provider_reference", "created_at")
    list_filter = ("provider", "status")
    search_fields = ("order__reference", "provider_reference")
    readonly_fields = ("created_at", "completed_at", "provider_payload")


@admin.register(WebhookEvent)
class WebhookEventAdmin(ModelAdmin):
    list_display = ("provider", "event_id", "signature_valid", "processed", "received_at")
    list_filter = ("provider", "processed", "signature_valid")
    search_fields = ("event_id",)
    readonly_fields = ("received_at", "processed_at", "payload")
