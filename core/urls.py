from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.landing_home, name="home"),
    path("demande/", views.shop_request, name="shop_request"),
    path("demande/merci/", views.shop_request_confirmation, name="shop_request_confirmation"),
]
