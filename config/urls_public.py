"""URLs pour djayma.sn (landing, auth publique)."""
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from core import views_pwa

urlpatterns = [
    path("", include("core.urls")),
    path("comptes/", include("accounts.urls")),
    path("manifest.webmanifest", views_pwa.manifest, name="manifest"),
    path("sw.js", views_pwa.service_worker, name="service_worker"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    try:
        import debug_toolbar
        urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
    except ImportError:
        pass
