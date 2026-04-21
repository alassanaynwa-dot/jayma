from django.urls import path
from . import views

app_name = "coupons_dashboard"

urlpatterns = [
    path("", views.coupon_list, name="list"),
    path("ajouter/", views.coupon_create, name="create"),
    path("<int:pk>/", views.coupon_edit, name="edit"),
    path("<int:pk>/supprimer/", views.coupon_delete, name="delete"),
]
