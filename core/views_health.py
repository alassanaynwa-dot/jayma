"""Healthcheck endpoint — pour uptime monitoring (Uptime Robot, etc.).

Renvoie 200 si tous les services critiques (DB, Redis) répondent. Sinon 503.
Pas d'auth, pas de CSRF, pas de log Sentry sur les checks healthy.
"""
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse


def _check_db() -> tuple[bool, str | None]:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as e:  # pragma: no cover
        return False, str(e)[:200]
    return True, None


def _check_cache() -> tuple[bool, str | None]:
    try:
        cache.set("healthz_probe", "ok", timeout=2)
        if cache.get("healthz_probe") != "ok":
            return False, "set/get mismatch"
    except Exception as e:  # pragma: no cover
        return False, str(e)[:200]
    return True, None


def healthz(request):
    db_ok, db_err = _check_db()
    cache_ok, cache_err = _check_cache()
    healthy = db_ok and cache_ok

    payload = {
        "status": "ok" if healthy else "degraded",
        "db": "ok" if db_ok else f"error: {db_err}",
        "cache": "ok" if cache_ok else f"error: {cache_err}",
    }
    status_code = 200 if healthy else 503
    response = JsonResponse(payload, status=status_code)
    response["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response
