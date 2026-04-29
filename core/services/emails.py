"""Helper unifié d'envoi d'emails branded Jappesi.

Tous les emails transactionnels passent par cette fonction. Elle :
- Charge les templates HTML + texte (`emails/<name>.html` + `emails/<name>.txt`)
- Envoie un message multipart (HTML + fallback texte)
- Utilise DEFAULT_FROM_EMAIL comme expéditeur

Usage:
    from core.services.emails import send_branded_email

    send_branded_email(
        subject="Bienvenue sur Jappesi",
        recipients=["alice@example.com"],
        template_name="merchant_welcome",
        context={"shop": shop, "owner": owner, "public_url": ..., ...},
    )
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger("jayma")


def send_branded_email(
    *,
    subject: str,
    recipients: list[str] | str,
    template_name: str,
    context: dict,
    fail_silently: bool = False,
) -> bool:
    """Envoie un email HTML + texte. Retourne True si envoyé, False sinon."""
    if isinstance(recipients, str):
        recipients = [recipients]
    recipients = [r for r in recipients if r]
    if not recipients:
        logger.warning("send_branded_email: pas de destinataire pour %s", template_name)
        return False

    full_context = {**context, "root_domain": settings.JAYMA_ROOT_DOMAIN}
    text_body = render_to_string(f"emails/{template_name}.txt", full_context)
    html_body = render_to_string(f"emails/{template_name}.html", full_context)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipients,
    )
    msg.attach_alternative(html_body, "text/html")

    try:
        msg.send(fail_silently=fail_silently)
        return True
    except Exception:
        logger.exception("Échec envoi email %s à %s", template_name, recipients)
        if not fail_silently:
            raise
        return False
