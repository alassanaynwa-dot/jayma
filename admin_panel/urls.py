from django.urls import path
from . import views

app_name = "admin_panel"

urlpatterns = [
    path("", views.admin_home, name="home"),
    path("demandes/", views.admin_requests, name="requests"),
    path("demandes/<int:pk>/approuver/", views.admin_request_approve, name="request_approve"),
    path("demandes/<int:pk>/rejeter/", views.admin_request_reject, name="request_reject"),
    path("boutiques/", views.admin_shops, name="shops"),
    path("commissions/", views.admin_commissions, name="commissions"),
    path("commissions/<int:pk>/payer/", views.admin_commission_mark_paid, name="commission_mark_paid"),
]
