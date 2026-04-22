"""URLs pour admin.djayma.sn — panneau owner plateforme Jayma."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from core import views_pwa

urlpatterns = [
    path("", include("admin_panel.urls")),
    path("django/", admin.site.urls),  # admin Django classique en fallback
    path("comptes/", include("accounts.urls")),  # login/logout/password
    path("manifest.webmanifest", views_pwa.manifest, name="manifest"),
    path("sw.js", views_pwa.service_worker, name="service_worker"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
