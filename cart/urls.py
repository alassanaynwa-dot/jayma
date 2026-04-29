from django.urls import path

from . import views

app_name = "cart"

urlpatterns = [
    path("", views.cart_view, name="view"),
    path("ajouter/<int:product_id>/", views.cart_add, name="add"),
    path("mettre-a-jour/<int:product_id>/", views.cart_update, name="update"),
    path("retirer/<int:product_id>/", views.cart_remove, name="remove"),
    path("vider/", views.cart_clear, name="clear"),
]
