"""URLs pour <slug>.jappesi.sn (boutique publique d'un commerçant)."""
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path

from core import views_pwa
from delivery.views import compute_fee_partial
from orders import views as orders_views

from django.urls import include

urlpatterns = [
    path("", include("shops.urls_public")),
    path("produits/", include("products.urls_public")),
    path("panier/", include("cart.urls")),
    path("commander/", include("orders.urls_public")),
    path("paiements/", include("payments.urls")),
    path("livreur/", include("delivery.urls_public")),
    path("promo/", include("coupons.urls_public")),
    path("compte/", include("accounts.urls_client")),

    # Suivi de commande public (sans compte, avec ref + phone)
    path("suivi/", orders_views.order_tracking, name="order_tracking"),

    # Calcul dynamique des frais de livraison (HTMX au checkout)
    path("api/frais-livraison/", compute_fee_partial, name="compute_fee"),

    # PWA
    path("manifest.webmanifest", views_pwa.manifest, name="manifest"),
    path("sw.js", views_pwa.service_worker, name="service_worker"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
