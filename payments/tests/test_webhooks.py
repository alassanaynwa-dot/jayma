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
    """OM webhooks doivent être cross-vérifiés via l'API OM avant encaissement."""

    @patch("payments.services.orange_money.check_transaction_status",
           return_value={"status": "SUCCESS"})
    def test_second_call_is_duplicate(self, mock_check, paying_order):
        # OM utilise txnid au lieu de provider_reference, on aligne
        order, payment = paying_order
        payment.provider = Payment.Provider.ORANGE_MONEY
        payment.provider_reference = "om_txn_999"
        payment.save()

        client = Client()
        body = json.dumps({
            "txnid": "om_txn_999", "status": "SUCCESS", "pay_token": "tok_abc",
        })

        r1 = client.post("/paiements/webhooks/orange-money/", body, content_type="application/json", HTTP_HOST="testshop.jayma.local")
        assert r1.status_code == 200

        r2 = client.post("/paiements/webhooks/orange-money/", body, content_type="application/json", HTTP_HOST="testshop.jayma.local")
        assert r2.status_code == 200
        assert r2.json().get("duplicate") is True

        assert WebhookEvent.objects.filter(provider="orange_money", event_id="om_txn_999").count() == 1

    @patch("payments.services.orange_money.check_transaction_status",
           return_value={"status": "FAILED"})
    def test_unconfirmed_by_api_returns_403_and_not_paid(self, mock_check, paying_order):
        """Webhook OM dit SUCCESS mais l'API dit FAILED → on rejette."""
        order, payment = paying_order
        payment.provider = Payment.Provider.ORANGE_MONEY
        payment.provider_reference = "om_fake_001"
        payment.save()

        client = Client()
        body = json.dumps({
            "txnid": "om_fake_001", "status": "SUCCESS", "pay_token": "tok_fake",
        })
        r = client.post(
            "/paiements/webhooks/orange-money/", body,
            content_type="application/json", HTTP_HOST="testshop.jayma.local",
        )
        assert r.status_code == 403
        order.refresh_from_db()
        assert order.payment_status == Order.PaymentStatus.PENDING

    def test_no_pay_token_returns_403(self, paying_order):
        """Webhook OM sans pay_token → impossible de cross-vérifier → rejet."""
        order, payment = paying_order
        payment.provider = Payment.Provider.ORANGE_MONEY
        payment.provider_reference = "om_notoken"
        payment.save()

        client = Client()
        body = json.dumps({"txnid": "om_notoken", "status": "SUCCESS"})  # pas de pay_token
        r = client.post(
            "/paiements/webhooks/orange-money/", body,
            content_type="application/json", HTTP_HOST="testshop.jayma.local",
        )
        assert r.status_code == 403
        order.refresh_from_db()
        assert order.payment_status == Order.PaymentStatus.PENDING


@pytest.mark.django_db
class TestCinetPayWebhookSecurity:
    """CinetPay : signature HMAC obligatoire + cross-check API."""

    def _make_signed_post(self, client, order_ref, secret_key="test-secret"):
        """Helper : forge un POST CinetPay avec signature HMAC valide."""
        import hashlib
        import hmac
        from urllib.parse import urlencode
        payload = {
            "cpm_trans_id": order_ref,
            "cpm_result": "00",
            "cpm_amount": "11000",
        }
        raw_body = urlencode(payload).encode()
        token = hmac.new(secret_key.encode(), raw_body, hashlib.sha256).hexdigest()
        return client.post(
            "/paiements/webhooks/cinetpay/",
            data=raw_body,
            content_type="application/x-www-form-urlencoded",
            HTTP_X_TOKEN=token,
            HTTP_HOST="testshop.jayma.local",
        )

    def test_no_signature_header_returns_403(self, paying_order):
        order, payment = paying_order
        payment.provider = Payment.Provider.CINETPAY
        payment.provider_reference = "cp_no_sig"
        payment.save()
        client = Client()
        r = client.post(
            "/paiements/webhooks/cinetpay/",
            data={"cpm_trans_id": "cp_no_sig", "cpm_result": "00"},
            HTTP_HOST="testshop.jayma.local",
        )
        assert r.status_code == 403
        order.refresh_from_db()
        assert order.payment_status == Order.PaymentStatus.PENDING

    @patch("payments.services.cinetpay.verify_hmac", return_value=False)
    def test_invalid_signature_returns_403(self, mock_verify, paying_order):
        order, payment = paying_order
        payment.provider = Payment.Provider.CINETPAY
        payment.provider_reference = "cp_bad_sig"
        payment.save()
        client = Client()
        r = client.post(
            "/paiements/webhooks/cinetpay/",
            data={"cpm_trans_id": "cp_bad_sig", "cpm_result": "00"},
            HTTP_X_TOKEN="forged",
            HTTP_HOST="testshop.jayma.local",
        )
        assert r.status_code == 403
        order.refresh_from_db()
        assert order.payment_status == Order.PaymentStatus.PENDING

    @patch("payments.services.cinetpay.verify_hmac", return_value=True)
    @patch("payments.services.cinetpay.check_payment_status",
           return_value={"data": {"status": "ACCEPTED"}})
    def test_valid_signature_and_api_confirmed_marks_paid(self, mock_check, mock_verify, paying_order):
        order, payment = paying_order
        payment.provider = Payment.Provider.CINETPAY
        payment.provider_reference = "cp_ok"
        payment.save()
        client = Client()
        r = client.post(
            "/paiements/webhooks/cinetpay/",
            data={"cpm_trans_id": "cp_ok", "cpm_result": "00"},
            HTTP_X_TOKEN="valid",
            HTTP_HOST="testshop.jayma.local",
        )
        assert r.status_code == 200
        order.refresh_from_db()
        assert order.payment_status == Order.PaymentStatus.PAID

    @patch("payments.services.cinetpay.verify_hmac", return_value=True)
    @patch("payments.services.cinetpay.check_payment_status",
           return_value={"data": {"status": "REFUSED"}})
    def test_signature_ok_but_api_refuses_returns_403(self, mock_check, mock_verify, paying_order):
        """HMAC valide mais l'API CinetPay dit REFUSED → on n'encaisse pas."""
        order, payment = paying_order
        payment.provider = Payment.Provider.CINETPAY
        payment.provider_reference = "cp_refused"
        payment.save()
        client = Client()
        r = client.post(
            "/paiements/webhooks/cinetpay/",
            data={"cpm_trans_id": "cp_refused", "cpm_result": "00"},
            HTTP_X_TOKEN="valid",
            HTTP_HOST="testshop.jayma.local",
        )
        assert r.status_code == 403
        order.refresh_from_db()
        assert order.payment_status == Order.PaymentStatus.PENDING

    @patch("payments.services.cinetpay.verify_hmac", return_value=True)
    @patch("payments.services.cinetpay.check_payment_status",
           return_value={"data": {"status": "ACCEPTED"}})
    def test_idempotent_second_call(self, mock_check, mock_verify, paying_order):
        order, payment = paying_order
        payment.provider = Payment.Provider.CINETPAY
        payment.provider_reference = "cp_idem"
        payment.save()
        client = Client()
        body = {"cpm_trans_id": "cp_idem", "cpm_result": "00"}
        r1 = client.post("/paiements/webhooks/cinetpay/", data=body,
                         HTTP_X_TOKEN="v", HTTP_HOST="testshop.jayma.local")
        assert r1.status_code == 200
        r2 = client.post("/paiements/webhooks/cinetpay/", data=body,
                         HTTP_X_TOKEN="v", HTTP_HOST="testshop.jayma.local")
        assert r2.status_code == 200  # OK (duplicate ignored)
        assert WebhookEvent.objects.filter(provider="cinetpay", event_id="cp_idem").count() == 1
