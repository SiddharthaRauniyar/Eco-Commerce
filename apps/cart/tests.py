"""Cart and checkout flow tests for the server-authoritative shopping phase."""

from datetime import timedelta
from decimal import Decimal

from django.core import mail
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.cart.models import Cart
from apps.cart.forms import AddToCartForm
from apps.cart.services import checkout_cash_on_delivery
from apps.categories.models import Category
from apps.coupons.models import Coupon
from apps.orders.models import Order
from apps.payments.models import Payment
from apps.products.models import InventoryAdjustment, Product, ProductVariant
from apps.wishlist.models import Wishlist


class CartCheckoutTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Audio", slug="audio")
        self.product = Product.objects.create(
            category=category,
            name="Checkout headphones",
            slug="checkout-headphones",
            sku="HEAD-CHECKOUT-001",
            description="A product used in checkout tests.",
            base_price=Decimal("100.00"),
            stock_quantity=8,
            status=Product.Status.ACTIVE,
        )
        now = timezone.now()
        self.coupon = Coupon.objects.create(
            code="SAVE10",
            discount_type=Coupon.DiscountType.FIXED,
            amount=Decimal("10.00"),
            starts_at=now - timedelta(days=1),
            ends_at=now + timedelta(days=1),
        )

    def _add_product(self):
        return self.client.post(reverse("cart:add", kwargs={"product_id": self.product.pk}), {"quantity": 2})

    def _checkout_data(self, token):
        return {
            "checkout_token": token,
            "email": "guest@example.com",
            "shipping_method": "standard",
            "shipping_recipient_name": "Guest Customer",
            "shipping_line1": "1 Market Street",
            "shipping_line2": "",
            "shipping_city": "Kathmandu",
            "shipping_region": "Bagmati",
            "shipping_postal_code": "44600",
            "shipping_country_code": "NP",
            "shipping_phone_number": "+977-9800000000",
            "billing_same_as_shipping": "on",
        }

    def test_cart_add_and_coupon_are_server_calculated(self):
        response = self._add_product()
        self.assertRedirects(response, reverse("cart:detail"))

        coupon_response = self.client.post(reverse("cart:coupon"), {"code": self.coupon.code})
        self.assertRedirects(coupon_response, reverse("cart:detail"))
        cart = Cart.objects.get(is_active=True)
        self.assertEqual(cart.items.get().quantity, 2)
        self.assertEqual(cart.coupon, self.coupon)

        page = self.client.get(reverse("cart:detail"))
        self.assertContains(page, "190.00")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_guest_cod_checkout_reserves_stock_creates_order_and_is_idempotent(self):
        self._add_product()
        checkout_page = self.client.get(reverse("cart:checkout"))
        token = checkout_page.context["checkout_token"]

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("cart:checkout"), self._checkout_data(token))
        order = Order.objects.get()
        self.assertRedirects(response, reverse("orders:confirmation", kwargs={"order_number": order.order_number}))
        self.assertEqual(order.guest_email, "guest@example.com")
        self.assertEqual(order.grand_total, Decimal("210.00"))
        self.assertEqual(order.items.get().quantity, 2)
        self.assertEqual(Payment.objects.get().provider, Payment.Provider.CASH_ON_DELIVERY)
        self.assertEqual(InventoryAdjustment.objects.get().delta, -2)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 6)
        self.assertFalse(Cart.objects.get().is_active)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [order.guest_email])
        self.assertIn(order.order_number, mail.outbox[0].body)
        self.assertIn(self.product.name, mail.outbox[0].body)

        retried_order = checkout_cash_on_delivery(
            cart=Cart.objects.get(), data=self._checkout_data(token), user=None, idempotency_key=token
        )
        self.assertEqual(retried_order.pk, order.pk)
        self.assertEqual(Order.objects.count(), 1)

        confirmation = self.client.get(reverse("orders:confirmation", kwargs={"order_number": order.order_number}))
        self.assertContains(confirmation, order.order_number)

    def test_wishlist_requires_authentication_and_saves_an_active_product(self):
        add_url = reverse("wishlist:add", kwargs={"product_id": self.product.pk})
        response = self.client.post(add_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

        user = CustomUser.objects.create_user("wishlist@example.com", "safe-test-password")
        self.client.force_login(user)
        response = self.client.post(add_url)
        self.assertRedirects(response, reverse("products:detail", kwargs={"slug": self.product.slug}))
        self.assertTrue(Wishlist.objects.get(user=user).products.filter(pk=self.product.pk).exists())

    def test_checkout_rejects_an_expired_token_before_creating_an_order(self):
        self._add_product()

        response = self.client.post(reverse("cart:checkout"), self._checkout_data("expired-token"))

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Order.objects.exists())

    def test_variant_choices_render_without_one_product_query_per_option(self):
        for index in range(4):
            ProductVariant.objects.create(
                product=self.product,
                name=f"Finish {index}",
                sku=f"HEAD-CHECKOUT-{index}",
            )
        form = AddToCartForm(self.product)

        with CaptureQueriesContext(connection) as queries:
            labels = [str(variant) for variant in form.fields["variant"].queryset]
        self.assertEqual(len(labels), 4)
        self.assertEqual(len(queries), 1)
