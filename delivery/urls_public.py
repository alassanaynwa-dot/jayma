from django.urls import path

from . import views

app_name = "delivery_portal"

urlpatterns = [
    path("<str:token>/", views.portal_home, name="home"),
    path("<str:token>/<str:reference>/", views.portal_order_detail, name="order"),
    path("<str:token>/<str:reference>/livree/", views.portal_mark_delivered, name="mark_delivered"),
]
