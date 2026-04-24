"""Réinitialisation mot de passe d'un commerçant par l'admin plateforme."""
import logging
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail

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
    try:
        send_mail(
            subject="Ton mot de passe Jappesi a été réinitialisé",
            message=(
                f"Bonjour {user.first_name or user.username},\n\n"
                f"L'équipe Jappesi a réinitialisé ton mot de passe.\n\n"
                f"  Identifiant           : {user.username}\n"
                f"  Nouveau mot de passe  : {new_pw}\n\n"
                f"Connecte-toi sur https://dashboard.{root} et change-le immédiatement "
                f"depuis Paramètres → Mot de passe.\n\n"
                f"— L'équipe Jappesi"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email] if user.email else [],
            fail_silently=True,
        )
    except Exception:
        logger.exception("Échec email reset pour user %s", user.pk)

    return new_pw
