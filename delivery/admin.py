from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Courier


@admin.register(Courier)
class CourierAdmin(ModelAdmin):
    list_display = ("name", "shop", "phone", "vehicle", "is_active")
    list_filter = ("vehicle", "is_active", "shop")
    search_fields = ("name", "phone", "shop__name")
    autocomplete_fields = ("shop",)
