"""Décorateurs d'accès — vérifient le rôle après login."""
from functools import wraps

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


def merchant_required(view_func):
    """
    Exige un user connecté avec role=merchant ET une boutique approuvée.
    Si l'utilisateur est un platform_admin, il est redirigé vers admin.
    Sinon page 403 propre.
    """

    @wraps(view_func)
    @login_required(login_url="/comptes/login/")
    def wrapper(request, *args, **kwargs):
        user = request.user

        host = request.get_host()
        port = ":" + host.split(":", 1)[1] if ":" in host else ""
        root = settings.JAYMA_ROOT_DOMAIN

        # Admin plateforme → on l'envoie sur son propre panneau
        if user.is_platform_admin and not user.is_merchant:
            return redirect(f"//admin.{root}{port}/")

        if not user.is_merchant:
            return render(request, "accounts/403_wrong_tenant.html", {
                "title": "Espace commerçant réservé",
                "message": "Cet espace est réservé aux commerçants Jappesi.",
                "redirect_url": f"//{root}{port}/",
                "redirect_label": "Retour à l'accueil",
            }, status=403)

        shop = getattr(user, "shop", None)
        if shop is None:
            return render(request, "accounts/no_shop.html", status=403)
        if not shop.is_approved:
            return render(request, "shops/pending_approval.html", {"shop": shop}, status=403)

        # Exposer shop sur la request pour les vues dashboard
        request.merchant_shop = shop
        return view_func(request, *args, **kwargs)

    return wrapper
