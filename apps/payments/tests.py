"""Focused checks for provider-gated checkout and idempotent payment completion."""

import hashlib
import hmac
import json
import time
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.cart.models import Cart
from apps.cart.services import checkout_online_payment
from apps.categories.models import Category
from apps.orders.models import Order
from apps.payments.models import Payment
from apps.products.models import Product


class PaymentFlowTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Payments", slug="payments")
        self.product = Product.objects.create(
            category=category,
            name="Payment test product",
            slug="payment-test-product",
            sku="PAYMENT-TEST-001",
            description="A product used for payment tests.",
            base_price=Decimal("100.00"),
            stock_quantity=8,
            status=Product.Status.ACTIVE,
        )

    def _add_product(self):
        self.client.post(reverse("cart:add", kwargs={"product_id": self.product.pk}), {"quantity": 2})

    def _checkout_data(self, token, **overrides):
        return {
            "checkout_token": token,
            "email": "guest@example.com",
            "payment_method": Payment.Provider.STRIPE,
            "shipping_method": "standard",
            "shipping_recipient_name": "Guest Customer",
            "shipping_line1": "1 Market Street",
            "shipping_city": "Kathmandu",
            "shipping_postal_code": "44600",
            "shipping_country_code": "NP",
            "billing_same_as_shipping": "on",
            **overrides,
        }

    @override_settings(STRIPE_SECRET_KEY="sk_test_example", STRIPE_WEBHOOK_SECRET="whsec_example")
    def test_stripe_checkout_creates_a_pending_order_before_redirecting(self):
        self._add_product()
        checkout_page = self.client.get(reverse("cart:checkout"))
        token = checkout_page.context["checkout_token"]

        with patch("apps.cart.views.create_stripe_checkout", return_value="https://checkout.stripe.test/session"):
            response = self.client.post(reverse("cart:checkout"), self._checkout_data(token))

        order = Order.objects.get()
        payment = Payment.objects.get()
        self.assertRedirects(response, "https://checkout.stripe.test/session", fetch_redirect_response=False)
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.payment_status, Order.PaymentStatus.PENDING)
        self.assertEqual(payment.provider, Payment.Provider.STRIPE)
        self.assertTrue(payment.expires_at)
        self.assertFalse(Cart.objects.get(pk=payment.cart_id).is_active)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 6)

    @override_settings(
        STRIPE_WEBHOOK_SECRET="whsec_example",
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_verified_stripe_webhook_marks_the_order_paid_only_once(self):
        self._add_product()
        cart = Cart.objects.get(is_active=True)
        payment = checkout_online_payment(
            cart=cart,
            data=self._checkout_data("stripe-webhook"),
            user=None,
            idempotency_key="stripe-webhook",
        )
        payment.external_payment_id = "cs_test_verified"
        payment.save(update_fields=("external_payment_id", "updated_at"))
        payload = json.dumps(
            {
                "id": "evt_test_verified",
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": payment.external_payment_id,
                        "payment_status": "paid",
                        "currency": "usd",
                        "amount_total": 21000,
                        "payment_intent": "pi_test_verified",
                    }
                },
            },
            separators=(",", ":"),
        ).encode()
        timestamp = str(int(time.time()))
        signature = hmac.new(
            b"whsec_example", timestamp.encode() + b"." + payload, hashlib.sha256
        ).hexdigest()

        with self.captureOnCommitCallbacks(execute=True):
            for _ in range(2):
                response = self.client.post(
                    reverse("payments:stripe_webhook"),
                    payload,
                    content_type="application/json",
                    HTTP_STRIPE_SIGNATURE=f"t={timestamp},v1={signature}",
                )
                self.assertEqual(response.status_code, 204)

        payment.refresh_from_db()
        payment.order.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCEEDED)
        self.assertEqual(payment.order.payment_status, Order.PaymentStatus.PAID)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 6)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [payment.order.guest_email])
        self.assertIn(payment.order.order_number, mail.outbox[0].body)

    def test_expired_online_payment_releases_stock_and_reopens_the_cart(self):
        self._add_product()
        cart = Cart.objects.get(is_active=True)
        payment = checkout_online_payment(
            cart=cart,
            data=self._checkout_data("expired-payment"),
            user=None,
            idempotency_key="expired-payment",
        )
        payment.expires_at = timezone.now() - timedelta(seconds=1)
        payment.save(update_fields=("expires_at", "updated_at"))

        call_command("expire_pending_payments")

        payment.refresh_from_db()
        cart.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertTrue(cart.is_active)
        self.assertEqual(self.product.stock_quantity, 8)
