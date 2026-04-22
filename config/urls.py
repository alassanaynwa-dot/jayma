"""
URLconf par défaut — utilisé uniquement comme fallback.

Le TenantMiddleware écrase request.urlconf selon le sous-domaine détecté :
- djayma.sn              → config.urls_public
- dashboard.djayma.sn    → config.urls_dashboard
- admin.djayma.sn        → config.urls_admin
- <slug>.djayma.sn       → config.urls_shop
"""
from .urls_public import urlpatterns  # noqa: F401
