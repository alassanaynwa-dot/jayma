from django.urls import path
from . import views

app_name = "admin_panel"

urlpatterns = [
    path("", views.admin_home, name="home"),

    # Demandes
    path("demandes/", views.admin_requests, name="requests"),
    path("demandes/<int:pk>/approuver/", views.admin_request_approve, name="request_approve"),
    path("demandes/<int:pk>/rejeter/", views.admin_request_reject, name="request_reject"),

    # Boutiques
    path("boutiques/", views.admin_shops, name="shops"),
    path("boutiques/<int:pk>/", views.admin_shop_detail, name="shop_detail"),
    path("boutiques/<int:pk>/toggle-active/", views.admin_shop_toggle_active, name="shop_toggle_active"),
    path("boutiques/<int:pk>/commission/", views.admin_shop_update_commission, name="shop_update_commission"),
    path("boutiques/<int:pk>/reset-password/", views.admin_shop_reset_password, name="shop_reset_password"),

    # Commandes cross-boutique
    path("commandes/", views.admin_orders, name="orders"),
    path("commandes/<str:reference>/", views.admin_order_detail, name="order_detail"),

    # Clients cross-boutique
    path("clients/", views.admin_clients, name="clients"),

    # Avis produits (modération)
    path("avis/", views.admin_reviews, name="reviews"),
    path("avis/<int:pk>/toggle-approuve/", views.admin_review_toggle_approved, name="review_toggle_approved"),

    # Commissions
    path("commissions/", views.admin_commissions, name="commissions"),
    path("commissions/export.csv", views.admin_commissions_export_csv, name="commissions_export_csv"),
    path("commissions/<int:pk>/payer/", views.admin_commission_mark_paid, name="commission_mark_paid"),

    # Récap mensuel
    path("mensuel/", views.admin_monthly, name="monthly"),

    # Logs notifications
    path("notifications/", views.admin_notifications, name="notifications"),

    # Webhooks providers
    path("webhooks/", views.admin_webhooks, name="webhooks"),
    path("webhooks/<int:pk>/", views.admin_webhook_detail, name="webhook_detail"),

    # Livreurs (cross-boutique)
    path("livreurs/", views.admin_couriers, name="couriers"),

    # Réglages plateforme
    path("reglages/", views.admin_settings, name="settings"),
    path("reglages/update/", views.admin_settings_update, name="settings_update"),

    # Catalogue cross-boutique
    path("produits/", views.admin_products, name="products"),
    path("produits/<int:pk>/toggle-active/", views.admin_product_toggle_active, name="product_toggle_active"),

    # Catégories agrégées
    path("categories/", views.admin_categories, name="categories"),

    # Journal d'audit
    path("audit/", views.admin_audit, name="audit"),

    # Utilisateurs (commerçants + admins)
    path("utilisateurs/", views.admin_users, name="users"),
    path("utilisateurs/<int:pk>/toggle-active/", views.admin_user_toggle_active, name="user_toggle_active"),
    path("utilisateurs/<int:pk>/relancer/", views.admin_user_send_reengage, name="user_send_reengage"),
]
