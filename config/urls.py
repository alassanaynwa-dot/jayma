"""
URLconf par défaut — utilisé uniquement comme fallback.

Le TenantMiddleware écrase request.urlconf selon le sous-domaine détecté :
- jappesi.sn              → config.urls_public
- dashboard.jappesi.sn    → config.urls_dashboard
- admin.jappesi.sn        → config.urls_admin
- <slug>.jappesi.sn       → config.urls_shop
"""
from .urls_public import urlpatterns  # noqa: F401
