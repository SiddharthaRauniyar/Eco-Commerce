"""Small integration tests for the public storefront home page."""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.categories.models import Category
from apps.products.models import Product


class StorefrontHomeTests(TestCase):
    def test_health_reports_ready_without_dependency_details(self):
        response = self.client.get(reverse("core:health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_home_shows_only_active_catalog_products(self):
        category = Category.objects.create(name="Audio", slug="audio")
        Product.objects.create(
            category=category,
            name="Featured headphones",
            slug="featured-headphones",
            sku="HEAD-001",
            description="A focused listening experience.",
            base_price=Decimal("99.00"),
            status=Product.Status.ACTIVE,
            is_featured=True,
        )
        Product.objects.create(
            category=category,
            name="Draft headphones",
            slug="draft-headphones",
            sku="HEAD-002",
            description="Not public.",
            base_price=Decimal("49.00"),
            status=Product.Status.DRAFT,
            is_featured=True,
        )

        response = self.client.get(reverse("core:home"))

        self.assertContains(response, "Featured headphones")
        self.assertNotContains(response, "Draft headphones")
        self.assertContains(response, reverse("products:catalog"))
