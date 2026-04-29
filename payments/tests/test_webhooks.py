"""Tests d'idempotence des webhooks paiement.

Les providers (Wave, Orange Money, CinetPay) peuvent retry leur callback
plusieurs fois si on répond avec un timeout ou un 5xx. Le code doit
détecter qu'un event_id a déjà été traité et ignorer la duplication SANS
re-déclencher mark_order_paid.
"""
import json
from unittest.mock import patch

import pytest
from django.test import Client

from orders.models import Order
from payments.models import Payment, WebhookEvent


@pytest.fixture
def paying_order(shop, product, db):
    """Une Order pending avec un Payment provider_reference="sess_test_42"."""
    order = Order.objects.create(
        shop=shop,
        client_name="Aïssatou Fall",
        client_phone="+221770001234",
        client_address="Rue 10 x 27",
        client_city="Dakar",
        subtotal_xof=10000,
        delivery_xof=1000,
        total_xof=11000,
        commission_rate=8,
        commission_xof=880,
        merchant_amount_xof=10120,
        payment_method=Order.PaymentMethod.WAVE,
        payment_status=Order.PaymentStatus.PENDING,
        status=Order.Status.PENDING,
    )
    payment = Payment.objects.create(
        order=order,
        provider=Payment.Provider.WAVE,
        amount_xof=11000,
        provider_reference="sess_test_42",
        status=Payment.Status.PENDING,
    )
    return order, payment


@pytest.mark.django_db
class TestWaveWebhookIdempotency:
    """Le webhook Wave doit être idempotent malgré les retries du provider."""

    @patch("payments.services.wave.verify_webhook_signature", return_value=True)
    def test_first_call_marks_order_paid(self, mock_verify, paying_order):
        order, payment = paying_order
        client = Client()
        body = json.dumps({
            "id": "evt_wave_12345",
            "type": "checkout.session.completed",
            "data": {"id": "sess_test_42"},
        })
        response = client.post(
            "/paiements/webhooks/wave/",
            data=body,
            content_type="application/json",
            HTTP_WAVE_SIGNATURE="abc",
            HTTP_HOST="testshop.jayma.local",
        )
        assert response.status_code == 200
        order.refresh_from_db()
        assert order.payment_status == Order.PaymentStatus.PAID

    @patch("payments.services.wave.verify_webhook_signature", return_value=True)
    def test_second_call_with_same_event_id_is_duplicate(self, mock_verify, paying_order):
        """Le second call avec le même event_id renvoie 'duplicate' sans rien refaire."""
        order, payment = paying_order
        client = Client()
        body = json.dumps({
            "id": "evt_wave_12345",
            "type": "checkout.session.completed",
            "data": {"id": "sess_test_42"},
        })

        # Premier call : OK
        response1 = client.post("/paiements/webhooks/wave/", body, content_type="application/json", HTTP_WAVE_SIGNATURE="abc", HTTP_HOST="testshop.jayma.local")
        assert response1.status_code == 200
        order.refresh_from_db()
        paid_at_first = order.paid_at
        assert paid_at_first is not None

        # Second call avec MÊME event_id
        response2 = client.post("/paiements/webhooks/wave/", body, content_type="application/json", HTTP_WAVE_SIGNATURE="abc", HTTP_HOST="testshop.jayma.local")
        assert response2.status_code == 200
        assert response2.json().get("duplicate") is True

        # paid_at ne doit PAS avoir changé : on n'a pas re-déclenché mark_order_paid
        order.refresh_from_db()
        assert order.paid_at == paid_at_first

        # Un seul WebhookEvent en BDD
        assert WebhookEvent.objects.filter(provider="wave", event_id="evt_wave_12345").count() == 1

    @patch("payments.services.wave.verify_webhook_signature", return_value=False)
    def test_invalid_signature_returns_403(self, mock_verify, paying_order):
        order, _ = paying_order
        client = Client()
        body = json.dumps({"id": "evt_xxx", "type": "checkout.session.completed", "data": {"id": "sess_test_42"}})
        response = client.post("/paiements/webhooks/wave/", body, content_type="application/json", HTTP_WAVE_SIGNATURE="bad", HTTP_HOST="testshop.jayma.local")
        assert response.status_code == 403

        # Order ne doit PAS être passée à PAID
        order.refresh_from_db()
        assert order.payment_status == Order.PaymentStatus.PENDING


@pytest.mark.django_db
class TestOrangeMoneyWebhookIdempotency:
    def test_second_call_is_duplicate(self, paying_order):
        # OM utilise txnid au lieu de provider_reference, on aligne
        order, payment = paying_order
        payment.provider = Payment.Provider.ORANGE_MONEY
        payment.provider_reference = "om_txn_999"
        payment.save()

        client = Client()
        body = json.dumps({"txnid": "om_txn_999", "status": "SUCCESS"})

        r1 = client.post("/paiements/webhooks/orange-money/", body, content_type="application/json", HTTP_HOST="testshop.jayma.local")
        assert r1.status_code == 200

        r2 = client.post("/paiements/webhooks/orange-money/", body, content_type="application/json", HTTP_HOST="testshop.jayma.local")
        assert r2.status_code == 200
        assert r2.json().get("duplicate") is True

        assert WebhookEvent.objects.filter(provider="orange_money", event_id="om_txn_999").count() == 1
