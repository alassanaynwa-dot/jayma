"""Décorateur pour les vues admin.jappesi.sn."""
from functools import wraps
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden


def platform_admin_required(view_func):
    """Exige un user connecté avec role=admin (ou superuser)."""

    @wraps(view_func)
    @login_required(login_url="/comptes/login/")
    def wrapper(request, *args, **kwargs):
        if not request.user.is_platform_admin:
            return HttpResponseForbidden("Accès réservé à l'équipe Jappesi.")
        return view_func(request, *args, **kwargs)

    return wrapper
