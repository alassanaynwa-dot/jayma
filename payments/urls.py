from django.urls import path
from . import views

app_name = "payments"

urlpatterns = [
    path("initier/<str:reference>/", views.payment_initiate, name="initiate"),
    path("retour/<str:reference>/",  views.payment_return,   name="return"),
    path("annule/<str:reference>/",  views.payment_cancel,   name="cancel"),

    # Mock dev
    path("mock/<str:reference>/",    views.payment_mock,         name="mock_page"),
    path("mock/<str:reference>/confirmer/", views.payment_mock_confirm, name="mock_confirm"),

    # Webhooks providers (appelés depuis l'extérieur)
    path("webhooks/wave/",         views.webhook_wave,         name="webhook_wave"),
    path("webhooks/orange-money/", views.webhook_orange_money, name="webhook_om"),
    path("webhooks/cinetpay/",     views.webhook_cinetpay,     name="webhook_cinetpay"),
]
