"""
URLconf par défaut — utilisé uniquement comme fallback.

Le TenantMiddleware écrase request.urlconf selon le sous-domaine détecté :
- jayma.sn              → config.urls_public
- dashboard.jayma.sn    → config.urls_dashboard
- admin.jayma.sn        → config.urls_admin
- <slug>.jayma.sn       → config.urls_shop
"""
from .urls_public import urlpatterns  # noqa: F401
