"""Access and permission-aware metric checks for the operations dashboard."""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.categories.models import Category
from apps.orders.models import Order
from apps.products.models import Product


class OperationsDashboardTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Dashboard", slug="dashboard")
        self.product = Product.objects.create(
            category=category,
            name="Low stock dashboard product",
            slug="low-stock-dashboard-product",
            sku="DASH-LOW-001",
            description="A product used for dashboard tests.",
            base_price=Decimal("100.00"),
            stock_quantity=1,
            reorder_level=1,
            status=Product.Status.ACTIVE,
        )
        self.customer = CustomUser.objects.create_user("customer@example.com", "safe-test-password")
        self.staff = CustomUser.objects.create_superuser("staff@example.com", "safe-test-password")
        Order.objects.create(
            order_number="SC-DASHBOARD-0001",
            user=self.customer,
            billing_address_snapshot={},
            shipping_address_snapshot={},
            status=Order.Status.CONFIRMED,
            payment_status=Order.PaymentStatus.PAID,
            currency="USD",
            subtotal=Decimal("200.00"),
            shipping_total=Decimal("10.00"),
            grand_total=Decimal("210.00"),
        )

    def test_staff_dashboard_shows_authorized_live_operations_data(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("admin_dashboard:overview"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Keep the store moving")
        self.assertContains(response, "USD 210.00")
        self.assertContains(response, self.product.name)
        self.assertContains(response, "SC-DASHBOARD-0001")

    def test_customer_cannot_access_staff_operations_dashboard(self):
        self.client.force_login(self.customer)

        response = self.client.get(reverse("admin_dashboard:overview"))

        self.assertEqual(response.status_code, 403)

    def test_staff_workspace_offers_permitted_management_tools(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("admin_dashboard:workspace"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Run the store from one calm workspace")
        self.assertContains(response, reverse("admin:products_product_add"))
        self.assertContains(response, reverse("admin:orders_order_changelist"))
        self.assertContains(response, reverse("admin:accounts_customuser_changelist"))
