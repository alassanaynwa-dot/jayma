from django.urls import path

from . import views

app_name = "shops_public"

urlpatterns = [
    path("", views.shop_public_home, name="home"),
]
