from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import Category, Product, ProductImage


class ProductImageInline(TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ("name", "shop", "position", "is_active")
    list_filter = ("is_active", "shop")
    search_fields = ("name", "shop__name")
    autocomplete_fields = ("shop",)


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ("name", "shop", "category", "price", "stock", "is_active", "is_featured")
    list_filter = ("is_active", "is_featured", "shop", "category")
    search_fields = ("name", "shop__name")
    autocomplete_fields = ("shop", "category")
    readonly_fields = ("created_at", "updated_at")
    inlines = [ProductImageInline]
