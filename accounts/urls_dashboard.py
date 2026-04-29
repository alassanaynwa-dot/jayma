from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard_home, name="home"),
    path("notifications/", views.check_notifications, name="check_notifications"),
]
