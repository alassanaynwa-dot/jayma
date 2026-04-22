from django.urls import path
from . import views, views_client, views_reviews

app_name = "products_public"

urlpatterns = [
    path("", views.product_list_public, name="list"),

    # Avis produits
    path("avis/commande/<str:reference>/",
         views_reviews.reviews_for_order, name="reviews_for_order"),
    path("avis/commande/<str:reference>/produit/<int:product_pk>/",
         views_reviews.submit_review, name="submit_review"),

    # Favoris + alerte stock (HTMX)
    path("<int:product_id>/favori/", views_client.toggle_favorite, name="toggle_favorite"),
    path("<int:product_id>/alerte-stock/", views_client.register_stock_alert, name="register_stock_alert"),

    # Fiche produit (en dernier — catch-all sur slug)
    path("<slug:slug>/", views.product_detail_public, name="detail"),
]
