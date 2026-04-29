"""
Settings communs à tous les environnements.

Les variables sensibles sont lues depuis .env via django-environ.
"""
from pathlib import Path

import environ

# ----------------------------------------------------------------
# Chemins
# ----------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ----------------------------------------------------------------
# Lecture de .env
# ----------------------------------------------------------------
env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    DEFAULT_COMMISSION_RATE=(str, "8.00"),
    USE_R2=(bool, False),
)

env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

# ----------------------------------------------------------------
# Sécurité
# ----------------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-dev-key-change-me")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

# ----------------------------------------------------------------
# Domaine racine Jappesi
# ----------------------------------------------------------------
JAYMA_ROOT_DOMAIN = env("JAYMA_ROOT_DOMAIN", default="jappesi.sn")

# ----------------------------------------------------------------
# Applications
# ----------------------------------------------------------------
DJANGO_APPS = [
    "unfold",           # admin Jappesi — doit être AVANT django.contrib.admin
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "django_htmx",
    "django_extensions",
    "django_celery_beat",
]

LOCAL_APPS = [
    "core",
    "accounts",
    "shops",
    "products",
    "cart",
    "orders",
    "payments",
    "commissions",
    "notifications",
    "admin_panel",
    "delivery",
    "coupons",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ----------------------------------------------------------------
# Middleware
# ----------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    # Middleware multi-tenant — détecte le sous-domaine et charge le shop
    "config.middleware.TenantMiddleware",
]

ROOT_URLCONF = "config.urls"

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ----------------------------------------------------------------
# Templates
# ----------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # Expose le shop courant dans tous les templates
                "shops.context_processors.current_shop",
                # Expose les URLs Jappesi (root, dashboard, admin) dynamiquement
                "shops.context_processors.jayma_urls",
            ],
        },
    },
]

# ----------------------------------------------------------------
# Base de données
# ----------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", default="jayma"),
        "USER": env("POSTGRES_USER", default="jayma"),
        "PASSWORD": env("POSTGRES_PASSWORD", default="jayma_dev"),
        "HOST": env("POSTGRES_HOST", default="localhost"),
        "PORT": env("POSTGRES_PORT", default="5434"),
        "CONN_MAX_AGE": 60,
    }
}

# ----------------------------------------------------------------
# Cache Redis
# ----------------------------------------------------------------
REDIS_URL = env("REDIS_URL", default="redis://localhost:6381/0")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "jayma",
    }
}

# Sessions en cache (plus rapide que DB)
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_CACHE_ALIAS = "default"

# ----------------------------------------------------------------
# Celery
# ----------------------------------------------------------------
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6381/1")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://localhost:6381/2")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Africa/Dakar"
CELERY_TASK_TRACK_STARTED = True

# ----------------------------------------------------------------
# Auth
# ----------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# ----------------------------------------------------------------
# i18n — Sénégal (français, FCFA)
# ----------------------------------------------------------------
LANGUAGE_CODE = "fr-sn"
TIME_ZONE = "Africa/Dakar"
USE_I18N = True
USE_TZ = True

# Format monétaire FCFA — XOF sans décimales
DECIMAL_SEPARATOR = ","
THOUSAND_SEPARATOR = " "
USE_THOUSAND_SEPARATOR = True

# ----------------------------------------------------------------
# Fichiers statiques & médias
# ----------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "static_collected"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ----------------------------------------------------------------
# Email
# ----------------------------------------------------------------
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=1026)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Jappesi <noreply@jappesi.sn>")

# ----------------------------------------------------------------
# Cookies (scopés par sous-domaine pour éviter le vol inter-boutiques)
# ----------------------------------------------------------------
# IMPORTANT : on NE MET PAS SESSION_COOKIE_DOMAIN = ".jappesi.sn"
# Chaque sous-domaine (dashboard, admin, boutique X) a sa propre session.
SESSION_COOKIE_NAME = "jayma_sid"
CSRF_COOKIE_NAME = "jayma_csrftoken"
CSRF_USE_SESSIONS = False

# ----------------------------------------------------------------
# SMS AfricasTalking
# ----------------------------------------------------------------
AT_USERNAME = env("AT_USERNAME", default="sandbox")
AT_API_KEY = env("AT_API_KEY", default="")
AT_SENDER_ID = env("AT_SENDER_ID", default="JAYMA")

# ----------------------------------------------------------------
# Paiements
# ----------------------------------------------------------------
WAVE_API_KEY = env("WAVE_API_KEY", default="")
WAVE_WEBHOOK_SECRET = env("WAVE_WEBHOOK_SECRET", default="")
WAVE_BUSINESS_ID = env("WAVE_BUSINESS_ID", default="")

OM_MERCHANT_KEY = env("OM_MERCHANT_KEY", default="")
OM_CLIENT_ID = env("OM_CLIENT_ID", default="")
OM_CLIENT_SECRET = env("OM_CLIENT_SECRET", default="")
OM_WEBHOOK_SECRET = env("OM_WEBHOOK_SECRET", default="")

CINETPAY_API_KEY = env("CINETPAY_API_KEY", default="")
CINETPAY_SITE_ID = env("CINETPAY_SITE_ID", default="")
CINETPAY_SECRET_KEY = env("CINETPAY_SECRET_KEY", default="")

# ----------------------------------------------------------------
# Commission plateforme
# ----------------------------------------------------------------
DEFAULT_COMMISSION_RATE = env("DEFAULT_COMMISSION_RATE")

# ----------------------------------------------------------------
# Auto field default
# ----------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ----------------------------------------------------------------
# Logging minimal
# ----------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "[{levelname}] {asctime} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {"level": "INFO", "propagate": True},
        "jayma": {"level": "DEBUG", "propagate": True},
    },
}
