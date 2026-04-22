from django.urls import path

from products.views_client import favorites_list
from . import views_client

app_name = "client"

urlpatterns = [
    path("connexion/", views_client.client_login, name="login"),
    path("verification/", views_client.client_verify_otp, name="verify_otp"),
    path("verification/renvoyer/", views_client.client_resend_otp, name="resend_otp"),
    path("deconnexion/", views_client.client_logout, name="logout"),

    path("", views_client.client_home, name="home"),
    path("adresses/", views_client.client_addresses, name="addresses"),
    path("adresses/ajouter/", views_client.address_create, name="address_create"),
    path("adresses/<int:pk>/", views_client.address_edit, name="address_edit"),
    path("adresses/<int:pk>/supprimer/", views_client.address_delete, name="address_delete"),

    # Favoris
    path("favoris/", favorites_list, name="favorites"),
]
