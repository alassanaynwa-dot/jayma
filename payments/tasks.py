"""Tâches Celery liées aux paiements."""
import logging

from celery import shared_task
from django.conf import settings

from core.services.emails import send_branded_email
from notifications.services.sms import send_sms
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
    order_url = f"https://dashboard.{settings.JAYMA_ROOT_DOMAIN}/commandes/{order.reference}/"

    send_branded_email(
        subject=f"💰 Nouveau paiement reçu — commande {order.reference}",
        recipients=[owner.email],
        template_name="merchant_payment_received",
        context={
            "order": order,
            "shop": shop,
            "owner": owner,
            "order_url": order_url,
            "recipient_label": owner.email,
        },
        fail_silently=True,
    )

    # SMS
    try:
        send_sms(
            owner.phone,
            f"Jappesi : commande {order.reference} payee ({order.total_xof} XOF). "
            f"Traite-la sur dashboard.{settings.JAYMA_ROOT_DOMAIN}"
        )
    except Exception:
        logger.exception("Échec SMS merchant pour order %s", order.reference)
