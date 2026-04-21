from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import Order, OrderItem


class OrderItemInline(TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product_name", "unit_price_xof", "quantity")


@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = ("reference", "shop", "client_name", "total_xof", "status", "payment_status", "created_at")
    list_filter = ("status", "payment_status", "payment_method", "shop")
    search_fields = ("reference", "client_name", "client_phone", "shop__name")
    readonly_fields = ("reference", "created_at", "updated_at", "paid_at", "delivered_at",
                       "subtotal_xof", "total_xof", "commission_xof", "merchant_amount_xof")
    inlines = [OrderItemInline]
