"""
Dispatcher paiements — délègue à Wave / Orange Money / CinetPay.

En dev (creds absentes) → MockProvider qui simule succès immédiat,
pour que le flow e2e soit testable sans comptes dev providers.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass

from django.conf import settings
from django.urls import reverse

from orders.models import Order
from payments.models import Payment

logger = logging.getLogger("jayma")


@dataclass
class PaymentInit:
    payment: Payment
    redirect_url: str | None
    mock: bool = False


def _absolute_url(request, name: str, **kwargs) -> str:
    return request.build_absolute_uri(reverse(name, kwargs=kwargs))


def initiate_payment(request, order: Order) -> PaymentInit:
    provider_map = {
        Order.PaymentMethod.WAVE: initiate_wave,
        Order.PaymentMethod.ORANGE_MONEY: initiate_orange_money,
        Order.PaymentMethod.CINETPAY: initiate_cinetpay,
    }
    initiator = provider_map.get(order.payment_method)
    if not initiator:
        raise ValueError(f"Méthode de paiement non supportée : {order.payment_method}")
    return initiator(request, order)


# ============== Wave ==============

def initiate_wave(request, order: Order) -> PaymentInit:
    payment = Payment.objects.create(
        order=order, provider=Payment.Provider.WAVE, amount_xof=order.total_xof,
    )
    if not settings.WAVE_API_KEY:
        return _mock_success(payment, order)

    from . import wave
    success_url = _absolute_url(request, "payments:return", reference=order.reference)
    cancel_url = _absolute_url(request, "payments:cancel", reference=order.reference)
    try:
        resp = wave.create_checkout_session(order, success_url, cancel_url)
    except wave.WaveError as exc:
        _mark_payment_failed(payment, str(exc))
        raise
    payment.provider_reference = resp.get("id", "")
    payment.provider_payload = resp
    payment.save()
    return PaymentInit(payment=payment, redirect_url=resp.get("wave_launch_url"))


# ============== Orange Money ==============

def initiate_orange_money(request, order: Order) -> PaymentInit:
    payment = Payment.objects.create(
        order=order, provider=Payment.Provider.ORANGE_MONEY, amount_xof=order.total_xof,
    )
    if not settings.OM_CLIENT_ID:
        return _mock_success(payment, order)

    from . import orange_money
    success_url = _absolute_url(request, "payments:return", reference=order.reference)
    cancel_url = _absolute_url(request, "payments:cancel", reference=order.reference)
    try:
        resp = orange_money.create_payment(order, success_url, cancel_url)
    except orange_money.OrangeMoneyError as exc:
        _mark_payment_failed(payment, str(exc))
        raise
    payment.provider_reference = resp.get("pay_token", "")
    payment.provider_payload = resp
    payment.save()
    return PaymentInit(payment=payment, redirect_url=resp.get("payment_url"))


# ============== CinetPay ==============

def initiate_cinetpay(request, order: Order) -> PaymentInit:
    payment = Payment.objects.create(
        order=order, provider=Payment.Provider.CINETPAY, amount_xof=order.total_xof,
    )
    if not settings.CINETPAY_API_KEY:
        return _mock_success(payment, order)

    from . import cinetpay
    return_url = _absolute_url(request, "payments:return", reference=order.reference)
    notify_url = _absolute_url(request, "payments:webhook_cinetpay")
    try:
        resp = cinetpay.create_payment(order, return_url, notify_url)
    except cinetpay.CinetPayError as exc:
        _mark_payment_failed(payment, str(exc))
        raise
    data = resp.get("data", {})
    payment.provider_reference = data.get("payment_token", "")
    payment.provider_payload = resp
    payment.save()
    return PaymentInit(payment=payment, redirect_url=data.get("payment_url"))


# ============== Helpers ==============

def _mock_success(payment: Payment, order: Order) -> PaymentInit:
    logger.warning("[MOCK] Pas de creds pour %s → mode simulation.", payment.get_provider_display())
    return PaymentInit(
        payment=payment,
        redirect_url=reverse("payments:mock_page", kwargs={"reference": order.reference}),
        mock=True,
    )


def _mark_payment_failed(payment: Payment, error_msg: str) -> None:
    payment.status = Payment.Status.FAILED
    payment.provider_payload = {"error": error_msg}
    payment.save()


def mark_order_paid(order: Order, payment: Payment, provider_payload: dict | None = None) -> None:
    """Marque Order+Payment comme payés (idempotent, notifie le commerçant)."""
    from django.utils import timezone
    if order.payment_status == Order.PaymentStatus.PAID:
        return

    payment.status = Payment.Status.SUCCESS
    payment.completed_at = timezone.now()
    if provider_payload:
        payment.provider_payload = provider_payload
    payment.save()

    order.payment_status = Order.PaymentStatus.PAID
    order.paid_at = timezone.now()
    if order.status == Order.Status.PENDING:
        order.status = Order.Status.CONFIRMED
    order.save()

    logger.info("Order %s PAID via %s", order.reference, payment.get_provider_display())

    # Notifier le commerçant (async best-effort)
    try:
        from payments.tasks import notify_merchant_payment_received
        notify_merchant_payment_received.delay(order.pk)
    except Exception:
        logger.exception("Échec dispatch notification merchant pour order %s", order.reference)
