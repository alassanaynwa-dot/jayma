from django.urls import path
from . import views

app_name = "products_public"

urlpatterns = [
    path("", views.product_list_public, name="list"),
    path("<slug:slug>/", views.product_detail_public, name="detail"),
]
