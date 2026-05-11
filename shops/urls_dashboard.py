from django.urls import path

from . import views

app_name = "shops_dashboard"

urlpatterns = [
    path("", views.shop_settings, name="settings"),
    path("liste-attente/", views.shop_waitlist_dashboard, name="waitlist"),
]
