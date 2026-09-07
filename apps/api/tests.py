"""High-value API checks for visibility, ownership, and JWT controls."""

from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.mfa import encrypt_totp_secret
from apps.accounts.models import CustomUser, UserProfile
from apps.categories.models import Category
from apps.orders.models import Order, OrderItem
from apps.products.models import Product, ProductVariant
from apps.security.models import LoginAttempt


class PublicCatalogAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.audio = Category.objects.create(name="Audio", slug="audio")
        self.hidden = Category.objects.create(name="Hidden", slug="hidden", is_active=False)
        self.product = Product.objects.create(
            category=self.audio,
            name="API headphones",
            slug="api-headphones",
            sku="API-HEAD-001",
            description="Public product description.",
            short_description="Public product.",
            base_price=Decimal("120.00"),
            stock_quantity=3,
            status=Product.Status.ACTIVE,
            metadata={"supplier": "private"},
        )
        ProductVariant.objects.create(
            product=self.product,
            name="Available finish",
            sku="API-HEAD-AVAILABLE",
            stock_quantity=2,
            is_active=True,
        )
        ProductVariant.objects.create(
            product=self.product,
            name="Hidden finish",
            sku="API-HEAD-HIDDEN",
            stock_quantity=99,
            is_active=False,
        )
        Product.objects.create(
            category=self.audio,
            name="Draft product",
            slug="draft-product",
            sku="API-DRAFT-001",
            description="Not public.",
            base_price=Decimal("10.00"),
            status=Product.Status.DRAFT,
        )
        Product.objects.create(
            category=self.hidden,
            name="Hidden category product",
            slug="hidden-category-product",
            sku="API-HIDDEN-001",
            description="Not public.",
            base_price=Decimal("10.00"),
            status=Product.Status.ACTIVE,
        )
        cache.clear()

    def test_catalog_returns_only_public_allowlisted_json(self):
        response = self.client.get(reverse("api:product-list"), {"q": "headphones", "sort": "invalid"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"].split(";")[0], "application/json")
        self.assertEqual([item["slug"] for item in response.json()["results"]], [self.product.slug])
        product = response.json()["results"][0]
        self.assertNotIn("stock_quantity", product)
        self.assertNotIn("reorder_level", product)
        self.assertNotIn("metadata", product)
        self.assertNotIn("sku", product)
        self.assertNotIn("Access-Control-Allow-Origin", response)
        self.assertNotIn("sessionid", response.cookies)

    def test_detail_hides_inactive_variants_and_nonpublic_products(self):
        response = self.client.get(reverse("api:product-detail", kwargs={"slug": self.product.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["name"] for item in response.json()["variants"]], ["Available finish"])
        self.assertEqual(
            self.client.get(reverse("api:product-detail", kwargs={"slug": "draft-product"})).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse("api:product-detail", kwargs={"slug": "hidden-category-product"})).status_code,
            404,
        )
        self.assertEqual(self.client.post(reverse("api:product-list"), {}, format="json").status_code, 405)

    def test_active_categories_are_public_without_private_routes(self):
        response = self.client.get(reverse("api:category-list"))

        self.assertEqual([item["slug"] for item in response.json()], [self.audio.slug])
        self.assertEqual(self.client.get("/api/v1/security/events/").status_code, 404)

    def test_default_catalog_response_is_cached_and_invalidated_after_a_commit(self):
        first = self.client.get(reverse("api:product-list"))
        self.assertEqual(first["Cache-Control"], "public, max-age=60")

        with self.assertNumQueries(0):
            cached = self.client.get(reverse("api:product-list"))
        self.assertEqual(cached.json(), first.json())

        self.product.short_description = "Updated catalog copy."
        with self.captureOnCommitCallbacks(execute=True):
            self.product.save(update_fields=("short_description", "updated_at"))
        refreshed = self.client.get(reverse("api:product-list"))
        self.assertEqual(refreshed.json()["results"][0]["short_description"], "Updated catalog copy.")


class CustomerAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(
            "api-customer@example.com", "safe-test-password", is_email_verified=True
        )
        self.other_user = CustomUser.objects.create_user(
            "other-api-customer@example.com", "safe-test-password", is_email_verified=True
        )
        category = Category.objects.create(name="Orders", slug="orders")
        self.product = Product.objects.create(
            category=category,
            name="Order product",
            slug="order-product",
            sku="API-ORDER-001",
            description="A purchasable API product.",
            base_price=Decimal("50.00"),
            stock_quantity=4,
            status=Product.Status.ACTIVE,
        )

    def _tokens(self, **data):
        payload = {"email": self.user.email, "password": "safe-test-password", **data}
        response = self.client.post(reverse("api:token"), payload, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def _authenticate(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self._tokens()['access']}")

    def _order(self, user, number):
        order = Order.objects.create(
            order_number=number,
            user=user,
            status=Order.Status.CONFIRMED,
            payment_status=Order.PaymentStatus.PENDING,
            currency="USD",
            subtotal=Decimal("50.00"),
            discount_total=Decimal("0.00"),
            tax_total=Decimal("0.00"),
            shipping_total=Decimal("0.00"),
            grand_total=Decimal("50.00"),
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            sku=self.product.sku,
            unit_price=Decimal("50.00"),
            quantity=1,
            line_total=Decimal("50.00"),
        )
        return order

    def test_jwt_refresh_rotation_and_revoke_work_without_a_session(self):
        tokens = self._tokens()
        self.assertNotIn("sessionid", self.client.cookies)

        refresh = self.client.post(reverse("api:token-refresh"), {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(refresh.status_code, 200, refresh.content)
        self.assertNotEqual(refresh.json()["refresh"], tokens["refresh"])
        self.assertEqual(
            self.client.post(reverse("api:token-refresh"), {"refresh": tokens["refresh"]}, format="json").status_code,
            401,
        )
        revoke = self.client.post(
            reverse("api:token-revoke"), {"refresh": refresh.json()["refresh"]}, format="json"
        )
        self.assertEqual(revoke.status_code, 200, revoke.content)
        self.assertEqual(
            self.client.post(
                reverse("api:token-refresh"), {"refresh": refresh.json()["refresh"]}, format="json"
            ).status_code,
            401,
        )

    def test_token_endpoint_enforces_mfa_and_shared_lockout(self):
        unverified_user = CustomUser.objects.create_user(
            "unverified-api-customer@example.com", "safe-test-password"
        )
        self.assertEqual(
            self.client.post(
                reverse("api:token"),
                {"email": unverified_user.email, "password": "safe-test-password"},
                format="json",
            ).status_code,
            401,
        )

        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.mfa_enabled = True
        profile.mfa_secret_encrypted = encrypt_totp_secret("JBSWY3DPEHPK3PXP")
        profile.save(update_fields=("mfa_enabled", "mfa_secret_encrypted", "updated_at"))

        self.assertEqual(
            self.client.post(
                reverse("api:token"),
                {"email": self.user.email, "password": "safe-test-password"},
                format="json",
            ).status_code,
            401,
        )
        with patch("apps.api.serializers.verify_totp", return_value=True):
            self.assertEqual(self._tokens(mfa_code="123456")["access"].count("."), 2)

        locked_user = CustomUser.objects.create_user(
            "locked-api-customer@example.com", "safe-test-password", is_email_verified=True
        )
        lockout_client = APIClient()
        lockout_meta = {"REMOTE_ADDR": "203.0.113.55"}
        with override_settings(LOGIN_FAILURE_LIMIT=2):
            for _ in range(2):
                lockout_client.post(
                    reverse("api:token"),
                    {"email": locked_user.email, "password": "wrong-password"},
                    format="json",
                    **lockout_meta,
                )
            response = lockout_client.post(
                reverse("api:token"),
                {"email": locked_user.email, "password": "safe-test-password"},
                format="json",
                **lockout_meta,
            )
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response)
        self.assertGreaterEqual(LoginAttempt.objects.filter(email=locked_user.email, successful=False).count(), 2)

    def test_customer_resources_are_owned_and_use_existing_order_service(self):
        own_order = self._order(self.user, "SC-API-OWN")
        other_order = self._order(self.other_user, "SC-API-OTHER")
        self._authenticate()

        self.assertEqual(self.client.get(reverse("api:me")).json()["email"], self.user.email)
        address = self.client.post(
            reverse("api:address-list"),
            {
                "label": "Home",
                "recipient_name": "API Customer",
                "line1": "1 Market Street",
                "city": "Kathmandu",
                "postal_code": "44600",
                "country_code": "np",
            },
            format="json",
        )
        self.assertEqual(address.status_code, 201, address.content)
        self.assertEqual(address.json()["country_code"], "NP")
        self.assertEqual(
            self.client.post(reverse("api:wishlist"), {"product_slug": self.product.slug}, format="json").status_code,
            201,
        )
        self.assertEqual([item["order_number"] for item in self.client.get(reverse("api:order-list")).json()["results"]], [own_order.order_number])
        self.assertEqual(
            self.client.get(reverse("api:order-detail", kwargs={"order_number": other_order.order_number})).status_code,
            404,
        )
        response = self.client.post(reverse("api:order-cancel", kwargs={"order_number": own_order.order_number}), {}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        own_order.refresh_from_db()
        self.assertEqual(own_order.status, Order.Status.CANCELLED)
