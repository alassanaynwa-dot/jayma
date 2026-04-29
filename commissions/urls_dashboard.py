from django.urls import path

from . import views

app_name = "commissions_dashboard"

urlpatterns = [
    path("", views.revenues_dashboard, name="revenues"),
]
