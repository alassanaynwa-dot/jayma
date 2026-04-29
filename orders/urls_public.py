from django.urls import path

from . import views

app_name = "orders_public"

urlpatterns = [
    path("", views.checkout, name="checkout"),
    path("<str:reference>/", views.order_confirmation, name="confirmation"),
    path("<str:reference>/noter/", views.rate_delivery, name="rate_delivery"),
]
