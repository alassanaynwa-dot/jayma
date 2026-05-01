from django.urls import path

from . import views

app_name = "products_dashboard"

urlpatterns = [
    path("", views.product_list_dashboard, name="list"),
    path("ajouter/", views.product_create, name="create"),
    path("<int:pk>/", views.product_edit, name="edit"),
    path("<int:pk>/supprimer/", views.product_delete, name="delete"),
    path("<int:pk>/toggle/", views.product_toggle_active, name="toggle_active"),

    # Packs de produits
    path("packs/", views.pack_list, name="pack_list"),
    path("packs/ajouter/", views.pack_create, name="pack_create"),
    path("packs/<int:pk>/", views.pack_edit, name="pack_edit"),
    path("packs/<int:pk>/supprimer/", views.pack_delete, name="pack_delete"),

    # Catégories
    path("categories/", views.category_list, name="category_list"),
    path("categories/wizard/", views.category_wizard, name="category_wizard"),
    path("categories/reorder/", views.category_reorder, name="category_reorder"),
    path("categories/ajouter/", views.category_create, name="category_create"),
    path("categories/<int:pk>/", views.category_edit, name="category_edit"),
    path("categories/<int:pk>/supprimer/", views.category_delete, name="category_delete"),
]
