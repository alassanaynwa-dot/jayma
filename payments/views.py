"""Vues paiements — init, return, webhooks providers."""
import logging

from django.contrib import messages
from django.http import Http404, HttpResponse, JsonResponse
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
    """Webhook OM — payload JSON.

    OM ne signe pas son webhook avec un HMAC natif. Pour éviter qu'un
    attaquant fake un POST avec status=SUCCESS, on cross-vérifie en
    rappelant l'API OM (/transactionstatus/<pay_token>) — seul ce statut
    fait foi. Sans pay_token, ou si l'API renvoie autre chose que SUCCESS,
    on log le webhook mais on n'encaisse PAS le paiement.
    """
    import json

    from .services import orange_money

    try:
        payload = json.loads(request.body or b"{}")
    except Exception:
        return JsonResponse({"error": "invalid_json"}, status=400)

    txn_id = payload.get("txnid", "")
    status = payload.get("status", "")
    pay_token = payload.get("pay_token", "")

    # Cross-check via API OM si le webhook prétend SUCCESS et qu'on a un
    # pay_token. C'est l'équivalent fonctionnel d'un HMAC : seule l'API
    # peut confirmer la vérité du paiement.
    api_confirmed = False
    if status == "SUCCESS" and pay_token:
        try:
            api_status = orange_money.check_transaction_status(pay_token)
            api_confirmed = api_status.get("status") == "SUCCESS"
        except orange_money.OrangeMoneyError as exc:
            logger.warning("Webhook OM cross-check échoué (txn=%s) : %s", txn_id, exc)

    evt = _log_webhook("orange_money", txn_id, payload, api_confirmed)
    if evt.processed:
        return JsonResponse({"ok": True, "duplicate": True})

    if not api_confirmed:
        # Webhook reçu mais non confirmé par l'API → potentiel fake. On log
        # et on rejette sans encaisser. Si OM réessaie plus tard avec un
        # statut confirmable, le webhook sera traité (processed=False ici).
        logger.warning("Webhook OM non confirmé par API (txn=%s, status=%s)", txn_id, status)
        return JsonResponse({"ok": False, "reason": "unconfirmed"}, status=403)

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
    """Webhook CinetPay — confirmation avec transaction_id.

    CinetPay signe son webhook via HMAC-SHA256 dans le header `x-token`.
    On vérifie obligatoirement la signature avant de traiter le paiement
    pour éviter qu'un attaquant fake un POST avec cpm_result=00.
    En complément (best practice CinetPay), on cross-vérifie via l'API
    /payment/check si la signature est OK.
    """
    from .services import cinetpay

    raw_body = request.body
    payload = request.POST.dict() or {}
    txn_id = payload.get("cpm_trans_id", "")

    # 1. Vérification HMAC obligatoire
    received_token = request.headers.get("X-Token", "")
    sig_ok = cinetpay.verify_hmac(raw_body, received_token) if received_token else False

    evt = _log_webhook("cinetpay", txn_id, payload, sig_ok)
    if not sig_ok:
        logger.warning("Webhook CinetPay signature invalide (txn=%s)", txn_id)
        return HttpResponse("FORBIDDEN", status=403)
    if evt.processed:
        return HttpResponse("OK")

    # 2. Cross-check via API CinetPay (best practice doc CinetPay)
    api_confirmed = False
    if payload.get("cpm_result") == "00":
        try:
            check = cinetpay.check_payment_status(txn_id)
            # CinetPay renvoie data.status = "ACCEPTED" pour un paiement valide
            api_confirmed = (check.get("data") or {}).get("status") == "ACCEPTED"
        except cinetpay.CinetPayError as exc:
            logger.warning("Webhook CinetPay cross-check échoué (txn=%s) : %s", txn_id, exc)

    if not api_confirmed:
        logger.warning("Webhook CinetPay non confirmé par API (txn=%s)", txn_id)
        return HttpResponse("UNCONFIRMED", status=403)

    payment = Payment.objects.filter(provider_reference=txn_id).first()
    if payment:
        mark_order_paid(payment.order, payment, payload)

    evt.processed = True
    from django.utils import timezone
    evt.processed_at = timezone.now()
    evt.save()
    return HttpResponse("OK")
