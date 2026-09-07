"""Customer order-management checks for ownership and state-changing actions."""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.cart.models import Cart
from apps.categories.models import Category
from apps.orders.models import Order, OrderItem, OrderRequest
from apps.products.models import InventoryAdjustment, Product


class CustomerOrderTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Order tests", slug="order-tests")
        self.product = Product.objects.create(
            category=category,
            name="Order test product",
            slug="order-test-product",
            sku="ORDER-TEST-001",
            description="A product used for order-management tests.",
            base_price=Decimal("100.00"),
            stock_quantity=12,
            status=Product.Status.ACTIVE,
        )
        self.user = CustomUser.objects.create_user("orders@example.com", "safe-test-password")
        self.other_user = CustomUser.objects.create_user("other@example.com", "safe-test-password")

    def _order(self, *, status=Order.Status.CONFIRMED, payment_status=Order.PaymentStatus.PENDING):
        order = Order.objects.create(
            order_number=f"SC-ORDER-{Order.objects.count() + 1:06d}",
            user=self.user,
            billing_address_snapshot={"recipient_name": "Order Customer", "line1": "1 Market Street", "city": "Kathmandu", "postal_code": "44600", "country_code": "NP"},
            shipping_address_snapshot={"recipient_name": "Order Customer", "line1": "1 Market Street", "city": "Kathmandu", "postal_code": "44600", "country_code": "NP"},
            status=status,
            payment_status=payment_status,
            currency="USD",
            subtotal=Decimal("200.00"),
            shipping_total=Decimal("10.00"),
            grand_total=Decimal("210.00"),
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            sku=self.product.sku,
            unit_price=Decimal("100.00"),
            quantity=2,
            line_total=Decimal("200.00"),
        )
        return order

    def test_customer_can_cancel_a_confirmed_cod_order_once_and_stock_is_restored(self):
        order = self._order()
        self.product.stock_quantity = 10
        self.product.save(update_fields=("stock_quantity", "updated_at"))
        self.client.force_login(self.user)

        response = self.client.post(reverse("orders:cancel", kwargs={"order_number": order.order_number}))

        self.assertRedirects(response, reverse("orders:detail", kwargs={"order_number": order.order_number}))
        order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(self.product.stock_quantity, 12)
        self.assertEqual(InventoryAdjustment.objects.filter(reason=InventoryAdjustment.Reason.RELEASED).count(), 1)

        self.client.post(reverse("orders:cancel", kwargs={"order_number": order.order_number}))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 12)

    def test_delivered_paid_order_accepts_return_then_refund_request(self):
        order = self._order(status=Order.Status.DELIVERED, payment_status=Order.PaymentStatus.PAID)
        self.client.force_login(self.user)

        return_response = self.client.post(
            reverse("orders:return_request", kwargs={"order_number": order.order_number}),
            {"return-reason": "The item is not suitable."},
        )
        refund_response = self.client.post(
            reverse("orders:refund_request", kwargs={"order_number": order.order_number}),
            {"refund-reason": "Please return the payment to the original method."},
        )

        self.assertEqual(return_response.status_code, 302)
        self.assertEqual(refund_response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.RETURN_REQUESTED)
        self.assertEqual(OrderRequest.objects.filter(order=order, status=OrderRequest.Status.REQUESTED).count(), 2)

    def test_reorder_uses_current_prices_and_customer_orders_are_private(self):
        order = self._order()
        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(reverse("orders:detail", kwargs={"order_number": order.order_number})).status_code, 404)

        self.client.force_login(self.user)
        response = self.client.post(reverse("orders:reorder", kwargs={"order_number": order.order_number}))

        self.assertRedirects(response, reverse("cart:detail"))
        self.assertEqual(Cart.objects.get(user=self.user, is_active=True).items.get().quantity, 2)

    def test_order_history_uses_the_annotated_item_count(self):
        self._order()
        self.client.force_login(self.user)

        response = self.client.get(reverse("orders:history"))

        self.assertContains(response, "1 item")

    def test_invoice_download_is_a_pdf_with_a_stable_number(self):
        order = self._order()
        self.client.force_login(self.user)

        response = self.client.get(reverse("orders:invoice", kwargs={"order_number": order.order_number}))

        order.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertIn(order.invoice_number.encode(), response.content)
