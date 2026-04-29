from django.urls import path

from . import views

app_name = "coupons_public"

urlpatterns = [
    path("appliquer/", views.apply_coupon, name="apply"),
    path("retirer/", views.remove_coupon, name="remove"),
]
