from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from unfold.admin import ModelAdmin
from django.contrib import admin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin, ModelAdmin):
    list_display = ("username", "email", "phone", "role", "city", "is_active", "date_joined")
    list_filter = ("role", "is_active", "city")
    search_fields = ("username", "email", "phone", "first_name", "last_name")

    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Infos Jayma", {"fields": ("role", "phone", "city", "phone_verified")}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("Infos Jayma", {"fields": ("role", "phone", "city")}),
    )
