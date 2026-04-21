"""Tâches Celery liées aux paiements."""
import logging
from celery import shared_task

from orders.models import Order

logger = logging.getLogger("jayma")


@shared_task
def notify_merchant_payment_received(order_id: int) -> None:
    """Notifie le commerçant (email + SMS) qu'un paiement a été reçu."""
    try:
        order = Order.objects.select_related("shop__owner").get(pk=order_id)
    except Order.DoesNotExist:
        return

    shop = order.shop
    owner = shop.owner

    # Email
    from django.core.mail import send_mail
    from django.conf import settings
    try:
        send_mail(
            subject=f"💰 Nouveau paiement reçu — commande {order.reference}",
            message=(
                f"Bonjour {owner.first_name or owner.username},\n\n"
                f"Bonne nouvelle : la commande {order.reference} sur {shop.name} a été payée.\n\n"
                f"  Client     : {order.client_name} ({order.client_phone})\n"
                f"  Méthode    : {order.get_payment_method_display()}\n"
                f"  Montant    : {order.total_xof} XOF\n"
                f"  À recevoir : {order.merchant_amount_xof} XOF (après commission Jayma)\n\n"
                f"Tu peux la traiter depuis ton dashboard :\n"
                f"https://dashboard.{settings.JAYMA_ROOT_DOMAIN}/commandes/{order.reference}/\n\n"
                f"— L'équipe Jayma"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[owner.email],
            fail_silently=True,
        )
    except Exception:
        logger.exception("Échec email merchant pour order %s", order.reference)

    # SMS
    try:
        from notifications.services.sms import send_sms
        send_sms(
            owner.phone,
            f"Jayma : commande {order.reference} payee ({order.total_xof} XOF). "
            f"Traite-la sur dashboard.{settings.JAYMA_ROOT_DOMAIN}"
        )
    except Exception:
        logger.exception("Échec SMS merchant pour order %s", order.reference)
