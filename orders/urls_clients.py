from django.urls import path
from . import views_clients

app_name = "clients_dashboard"

urlpatterns = [
    path("", views_clients.clients_list, name="list"),
    path("<str:phone>/", views_clients.client_detail, name="detail"),
]
