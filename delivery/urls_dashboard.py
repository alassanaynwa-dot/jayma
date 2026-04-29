from django.urls import path

from . import views

app_name = "delivery_dashboard"

urlpatterns = [
    path("", views.courier_list, name="list"),
    path("ajouter/", views.courier_create, name="create"),
    path("<int:pk>/", views.courier_detail, name="detail"),
    path("<int:pk>/modifier/", views.courier_edit, name="edit"),
    path("<int:pk>/supprimer/", views.courier_delete, name="delete"),
    path("<int:pk>/envoyer-lien/", views.courier_send_portal_link, name="send_portal_link"),

    # Zones tarifées
    path("zones/", views.zone_list, name="zone_list"),
    path("zones/ajouter/", views.zone_create, name="zone_create"),
    path("zones/<int:pk>/", views.zone_edit, name="zone_edit"),
    path("zones/<int:pk>/supprimer/", views.zone_delete, name="zone_delete"),
]
