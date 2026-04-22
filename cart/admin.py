from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import AbandonedCart


@admin.register(AbandonedCart)
class AbandonedCartAdmin(ModelAdmin):
    list_display = ("client_phone", "shop", "total_xof", "last_seen_at",
                    "reminded_at", "recovered_at")
    list_filter = ("shop", "reminded_at", "recovered_at")
    search_fields = ("client_phone", "client_name", "shop__name")
    readonly_fields = ("created_at", "last_seen_at", "items_json")
