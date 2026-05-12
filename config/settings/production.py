"""Settings de production."""
from .base import *  # noqa: F401, F403

DEBUG = False

# Garde-fou : SECRET_KEY doit être explicitement défini en prod (pas de
# fallback "insecure-dev-key-change-me" silencieux). Si la var d'env est
# absente, on échoue au démarrage plutôt que de risquer un déploiement
# avec une clé prévisible (qui casserait sessions, CSRF, signed cookies).
if not SECRET_KEY or SECRET_KEY.startswith("insecure-"):  # noqa: F405
    raise RuntimeError(
        "DJANGO_SECRET_KEY manquante ou non sécurisée en production. "
        "Génère une clé avec `python -c 'import secrets; "
        "print(secrets.token_urlsafe(50))'` et mets-la dans .env."
    )

# ALLOWED_HOSTS est fourni via .env en prod

# Sécurité HTTPS
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Email SMTP prod (réel)
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# SMS : vrai backend AfricasTalking
SMS_BACKEND = "notifications.services.sms.AfricasTalkingSMSBackend"

# Stockage fichiers : Cloudflare R2 (S3-compatible)
if env.bool("USE_R2", default=False):  # noqa: F405
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "bucket_name": env("R2_BUCKET_NAME"),  # noqa: F405
                "access_key": env("R2_ACCESS_KEY_ID"),  # noqa: F405
                "secret_key": env("R2_SECRET_ACCESS_KEY"),  # noqa: F405
                "endpoint_url": env("R2_ENDPOINT_URL"),  # noqa: F405
                "custom_domain": env("R2_PUBLIC_URL", default=None),  # noqa: F405
                "default_acl": None,
                "querystring_auth": False,
                "region_name": "auto",
            },
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

# Logging plus verbeux en prod (erreurs)
LOGGING["root"]["level"] = "WARNING"  # noqa: F405

# Sentry — monitoring erreurs prod (silencieux si SENTRY_DSN vide)
SENTRY_DSN = env("SENTRY_DSN", default="")  # noqa: F405
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
        environment="production",
    )
