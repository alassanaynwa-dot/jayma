from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Commission


@admin.register(Commission)
class CommissionAdmin(ModelAdmin):
    list_display = ("order", "shop", "sale_amount_xof", "commission_xof",
                    "merchant_amount_xof", "is_paid", "created_at")
    list_filter = ("is_paid", "shop")
    search_fields = ("order__reference", "shop__name", "payout_reference")
    readonly_fields = ("order", "shop", "sale_amount_xof", "rate",
                       "commission_xof", "merchant_amount_xof", "created_at")
