"""URLs pour dashboard.jappesi.sn (espace commerçant)."""
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from core import views_pwa

urlpatterns = [
    path("", include("accounts.urls_dashboard")),
    path("produits/", include("products.urls_dashboard")),
    path("commandes/", include("orders.urls_dashboard")),
    path("clients/", include("orders.urls_clients")),
    path("revenus/", include("commissions.urls_dashboard")),
    path("livreurs/", include("delivery.urls_dashboard")),
    path("promos/", include("coupons.urls_dashboard")),
    path("parametres/", include("shops.urls_dashboard")),
    path("comptes/", include("accounts.urls")),  # login/logout/password
    path("manifest.webmanifest", views_pwa.manifest, name="manifest"),
    path("sw.js", views_pwa.service_worker, name="service_worker"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
