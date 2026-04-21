from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Coupon, CouponUsage


@admin.register(Coupon)
class CouponAdmin(ModelAdmin):
    list_display = ("code", "shop", "type", "value", "uses_count", "max_uses", "is_active")
    list_filter = ("type", "is_active", "shop")
    search_fields = ("code", "shop__name")
    autocomplete_fields = ("shop",)


@admin.register(CouponUsage)
class CouponUsageAdmin(ModelAdmin):
    list_display = ("coupon", "client_phone", "order", "discount_xof", "used_at")
    list_filter = ("coupon__shop",)
    search_fields = ("client_phone", "coupon__code", "order__reference")
    autocomplete_fields = ("coupon",)
