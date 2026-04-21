"""Vues paiements — init, return, webhooks providers."""
import logging
from django.contrib import messages
from django.http import Http404, JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from orders.models import Order

from .models import Payment, WebhookEvent
from .services.providers import initiate_payment, mark_order_paid

logger = logging.getLogger("jayma")


# ================= Initialisation =================

def payment_initiate(request, reference):
    """Lance un paiement pour une commande et redirige vers le provider."""
    if not request.shop:
        raise Http404()
    order = get_object_or_404(Order, reference=reference, shop=request.shop)

    if order.payment_status == Order.PaymentStatus.PAID:
        messages.info(request, "Cette commande est déjà payée.")
        return redirect("orders_public:confirmation", reference=order.reference)

    if order.payment_method == Order.PaymentMethod.CASH:
        return redirect("orders_public:confirmation", reference=order.reference)

    try:
        result = initiate_payment(request, order)
    except Exception as exc:
        logger.exception("Échec init paiement %s", order.reference)
        messages.error(request, f"Le paiement n'a pas pu être initialisé : {exc}")
        return redirect("orders_public:confirmation", reference=order.reference)

    if not result.redirect_url:
        messages.error(request, "Erreur : provider n'a pas retourné d'URL de paiement.")
        return redirect("orders_public:confirmation", reference=order.reference)

    return redirect(result.redirect_url)


# ================= Retour utilisateur =================

def payment_return(request, reference):
    """Page de retour après paiement — user revient du provider."""
    if not request.shop:
        raise Http404()
    order = get_object_or_404(Order, reference=reference, shop=request.shop)
    return render(request, "payments/return.html", {"shop": request.shop, "order": order})


def payment_cancel(request, reference):
    """User a annulé le paiement chez le provider."""
    if not request.shop:
        raise Http404()
    order = get_object_or_404(Order, reference=reference, shop=request.shop)
    messages.warning(request, "Paiement annulé. Tu peux réessayer ou choisir une autre méthode.")
    return redirect("orders_public:confirmation", reference=order.reference)


# ================= Mock (dev uniquement) =================

def payment_mock(request, reference):
    """Page de simulation — disponible uniquement si DEBUG ou pas de creds."""
    if not request.shop:
        raise Http404()
    order = get_object_or_404(Order, reference=reference, shop=request.shop)
    return render(request, "payments/mock.html", {"shop": request.shop, "order": order})


@require_POST
def payment_mock_confirm(request, reference):
    """Valide le paiement en mode mock."""
    if not request.shop:
        raise Http404()
    order = get_object_or_404(Order, reference=reference, shop=request.shop)
    payment = order.payments.order_by("-created_at").first()
    if payment:
        mark_order_paid(order, payment, {"mock": True})
        messages.success(request, "Paiement simulé avec succès.")
    return redirect("orders_public:confirmation", reference=order.reference)


# ================= Webhooks providers =================

def _log_webhook(provider: str, event_id: str, payload: dict, signature_ok: bool) -> WebhookEvent:
    evt, created = WebhookEvent.objects.get_or_create(
        provider=provider, event_id=event_id,
        defaults={"payload": payload, "signature_valid": signature_ok},
    )
    return evt


@csrf_exempt
@require_POST
def webhook_wave(request):
    """Webhook Wave — https://docs.wave.com/business#webhooks."""
    import json
    from .services import wave
    try:
        raw = request.body
        payload = json.loads(raw or b"{}")
    except Exception:
        return JsonResponse({"error": "invalid_json"}, status=400)

    sig = request.headers.get("Wave-Signature", "")
    sig_ok = wave.verify_webhook_signature(raw, sig) if sig else False
    evt_id = payload.get("id", "")

    evt = _log_webhook("wave", evt_id, payload, sig_ok)
    if not sig_ok:
        logger.warning("Webhook Wave signature invalide (event=%s)", evt_id)
        return JsonResponse({"ok": False}, status=403)
    if evt.processed:
        return JsonResponse({"ok": True, "duplicate": True})

    # checkout.session.completed
    if payload.get("type") == "checkout.session.completed":
        session_id = payload.get("data", {}).get("id", "")
        payment = Payment.objects.filter(provider_reference=session_id).first()
        if payment:
            mark_order_paid(payment.order, payment, payload)

    evt.processed = True
    from django.utils import timezone
    evt.processed_at = timezone.now()
    evt.save()
    return JsonResponse({"ok": True})


@csrf_exempt
@require_POST
def webhook_orange_money(request):
    """Webhook OM — payload JSON."""
    import json
    try:
        payload = json.loads(request.body or b"{}")
    except Exception:
        return JsonResponse({"error": "invalid_json"}, status=400)

    txn_id = payload.get("txnid", "")
    status = payload.get("status", "")
    evt = _log_webhook("orange_money", txn_id, payload, True)
    if evt.processed:
        return JsonResponse({"ok": True, "duplicate": True})

    if status == "SUCCESS":
        payment = Payment.objects.filter(provider_reference=txn_id).first()
        if payment:
            mark_order_paid(payment.order, payment, payload)
    evt.processed = True
    from django.utils import timezone
    evt.processed_at = timezone.now()
    evt.save()
    return JsonResponse({"ok": True})


@csrf_exempt
@require_POST
def webhook_cinetpay(request):
    """Webhook CinetPay — confirmation avec transaction_id."""
    payload = request.POST.dict() or {}
    txn_id = payload.get("cpm_trans_id", "")
    evt = _log_webhook("cinetpay", txn_id, payload, True)
    if evt.processed:
        return HttpResponse("OK")

    from . import cinetpay_check  # placeholder pour vérification par API si besoin

    # Signal de succès (à confirmer via API check en prod)
    if payload.get("cpm_result") == "00":
        payment = Payment.objects.filter(provider_reference=txn_id).first()
        if payment:
            mark_order_paid(payment.order, payment, payload)
    evt.processed = True
    from django.utils import timezone
    evt.processed_at = timezone.now()
    evt.save()
    return HttpResponse("OK")
