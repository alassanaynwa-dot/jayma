from django.urls import path

from . import views, views_health

app_name = "core"

urlpatterns = [
    path("", views.landing_home, name="home"),
    path("demande/", views.shop_request, name="shop_request"),
    path("demande/merci/", views.shop_request_confirmation, name="shop_request_confirmation"),

    # Pages légales
    path("cgu/", views.legal_cgu, name="legal_cgu"),
    path("cgv/", views.legal_cgv, name="legal_cgv"),
    path("mentions-legales/", views.legal_mentions, name="legal_mentions"),
    path("confidentialite/", views.legal_confidentialite, name="legal_confidentialite"),

    # Healthcheck pour uptime monitoring
    path("healthz/", views_health.healthz, name="healthz"),
]
