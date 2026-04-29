"""Réinitialisation mot de passe d'un commerçant par l'admin plateforme."""
import logging
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model

from core.services.emails import send_branded_email

logger = logging.getLogger("jayma")
User = get_user_model()


def reset_merchant_password(user) -> str:
    """Génère un nouveau mot de passe pour un commerçant et l'envoie par SMS + email.

    Retourne le mot de passe en clair (utile pour l'afficher à l'admin une fois).
    """
    new_pw = secrets.token_urlsafe(10)
    user.set_password(new_pw)
    user.save()

    root = settings.JAYMA_ROOT_DOMAIN
    dashboard_url = f"https://dashboard.{root}"

    # SMS
    try:
        from notifications.services.sms import send_sms
        send_sms(
            user.phone,
            f"Jappesi : ton mot de passe a ete reinitialise. "
            f"Nouveau mdp : {new_pw}. Connexion : dashboard.{root}"
        )
    except Exception:
        logger.exception("Échec SMS reset pour user %s", user.pk)

    # Email
    if user.email:
        send_branded_email(
            subject="Ton mot de passe Jappesi a été réinitialisé",
            recipients=[user.email],
            template_name="merchant_password_reset",
            context={
                "user": user,
                "new_password": new_pw,
                "dashboard_url": dashboard_url,
                "recipient_label": user.email,
            },
            fail_silently=True,
        )

    return new_pw
