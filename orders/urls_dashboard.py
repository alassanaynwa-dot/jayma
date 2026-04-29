from django.urls import path

from delivery import views as delivery_views

from . import views

app_name = "orders_dashboard"

urlpatterns = [
    path("", views.orders_list, name="list"),
    path("<str:reference>/", views.order_detail, name="detail"),
    path("<str:reference>/status/", views.order_update_status, name="update_status"),
    path("<str:reference>/tracking/", views.order_update_tracking, name="update_tracking"),
    path("<str:reference>/assigner/", delivery_views.assign_courier, name="assign_courier"),
]
