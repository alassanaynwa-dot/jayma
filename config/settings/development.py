"""Settings de développement."""
from .base import *  # noqa: F401, F403

DEBUG = True

# En dev on accepte n'importe quel sous-domaine de jayma.local
ALLOWED_HOSTS = ["*"]

# CSRF — Django 4+ exige l'origin dans la liste pour les POST
CSRF_TRUSTED_ORIGINS = [
    "http://*.jayma.local",
    "http://*.jayma.local:8002",
    "http://jayma.local",
    "http://jayma.local:8002",
    "http://localhost:8002",
    "http://127.0.0.1:8002",
    "http://*.localhost:8002",
]

# Backend email : Mailpit (local) — envoie pour de vrai via SMTP
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# SMS : en dev on logge au lieu d'envoyer
SMS_BACKEND = "notifications.services.sms.ConsoleSMSBackend"

# Cookies non sécurisés (HTTP local)
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Django Debug Toolbar si dispo
try:
    import debug_toolbar  # noqa: F401

    INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
    MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")  # noqa: F405
    INTERNAL_IPS = ["127.0.0.1"]

    # DDT s'exécute AVANT TenantMiddleware, on ne peut pas utiliser
    # request.tenant_type. On regarde directement le host.
    _DDT_RESERVED = {"dashboard", "admin", "www", "api"}

    def _show_toolbar(request):
        if request.headers.get("HX-Request"):
            return False
        host = request.get_host().split(":")[0].lower()
        if host in ("localhost", "127.0.0.1") or host.startswith("127."):
            return True
        # Extraire le 1er label du host (ex: "dashboard" depuis "dashboard.jayma.local")
        first = host.split(".")[0]
        # Seul le tenant "public" (sans sous-domaine significatif) charge la DDT.
        # Si le host est "jayma.local" (pas de sous-domaine), first == "jayma" → OK.
        # Si c'est "dashboard.jayma.local", first == "dashboard" → off.
        # Si c'est "maboutique.jayma.local", first == "maboutique" → off (pas public).
        return first == "jayma"

    DEBUG_TOOLBAR_CONFIG = {"SHOW_TOOLBAR_CALLBACK": _show_toolbar}
except ImportError:
    pass
