"""Public catalog coverage without creating purchase behaviour prematurely."""

from decimal import Decimal

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.categories.models import Category
from apps.products.models import InventoryAdjustment, Product, ProductVariant
from apps.products.services import adjust_inventory
from apps.products.selectors import public_products
from apps.security.models import AuditLog


class PublicCatalogTests(TestCase):
    def setUp(self):
        self.audio = Category.objects.create(name="Audio", slug="audio")
        self.work = Category.objects.create(name="Work", slug="work")
        self.headphones = Product.objects.create(
            category=self.audio,
            name="Studio headphones",
            slug="studio-headphones",
            sku="HEAD-001",
            description="Detailed audio for focused listening.",
            short_description="Focused studio listening.",
            base_price=Decimal("299.00"),
            status=Product.Status.ACTIVE,
        )
        Product.objects.create(
            category=self.work,
            name="Desk lamp",
            slug="desk-lamp",
            sku="LAMP-001",
            description="A warm pool of light.",
            base_price=Decimal("149.00"),
            status=Product.Status.ACTIVE,
        )
        Product.objects.create(
            category=self.audio,
            name="Unreleased speaker",
            slug="unreleased-speaker",
            sku="SPKR-001",
            description="Hidden from public catalog.",
            base_price=Decimal("199.00"),
            status=Product.Status.DRAFT,
        )

    def test_catalog_searches_active_products_only(self):
        response = self.client.get(reverse("products:catalog"), {"q": "headphones"})

        self.assertContains(response, "Studio headphones")
        self.assertNotContains(response, "Unreleased speaker")

    def test_category_url_filters_the_public_catalog(self):
        response = self.client.get(reverse("products:category", kwargs={"slug": self.audio.slug}))

        self.assertContains(response, "Studio headphones")
        self.assertNotContains(response, "Desk lamp")

    def test_product_detail_is_public_for_active_product(self):
        response = self.client.get(reverse("products:detail", kwargs={"slug": self.headphones.slug}))

        self.assertContains(response, "Studio headphones")
        self.assertContains(response, "Detailed audio for focused listening.")

    def test_catalog_selector_loads_only_card_relations_until_detail_data_is_requested(self):
        ProductVariant.objects.create(
            product=self.headphones,
            name="Graphite",
            sku="HEAD-001-GRAPHITE",
        )
        with CaptureQueriesContext(connection) as catalog_queries:
            list(public_products())
        with CaptureQueriesContext(connection) as detail_queries:
            list(public_products(include_variants=True, include_attributes=True))

        self.assertEqual(len(catalog_queries), 2)
        self.assertEqual(len(detail_queries), 4)


class InventoryAdjustmentTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Audio", slug="audio")
        self.product = Product.objects.create(
            category=category,
            name="Inventory headphones",
            slug="inventory-headphones",
            sku="HEAD-INV-001",
            description="Tracked inventory.",
            base_price=Decimal("99.00"),
            stock_quantity=3,
        )
        self.staff = CustomUser.objects.create_user("catalog@example.com", "safe-test-password")

    def test_adjustment_changes_stock_and_creates_an_immutable_audit_trail(self):
        adjustment = adjust_inventory(
            product=self.product,
            delta=7,
            reason=InventoryAdjustment.Reason.RECEIVED,
            actor=self.staff,
            note="Initial delivery",
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(adjustment.delta, 7)
        self.assertEqual(InventoryAdjustment.objects.count(), 1)
        audit = AuditLog.objects.get(action="inventory.adjusted")
        self.assertEqual(audit.before["stock_quantity"], 3)
        self.assertEqual(audit.after["stock_quantity"], 10)

    def test_adjustment_cannot_make_stock_negative(self):
        with self.assertRaisesMessage(ValidationError, "would make stock negative"):
            adjust_inventory(
                product=self.product,
                delta=-4,
                reason=InventoryAdjustment.Reason.DAMAGED,
                actor=self.staff,
            )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 3)
        self.assertFalse(InventoryAdjustment.objects.exists())

    def test_admin_can_set_an_exact_stock_quantity_without_bypassing_the_ledger(self):
        staff = CustomUser.objects.create_superuser("inventory-admin@example.com", "safe-test-password")
        request = RequestFactory().post("/admin/products/product/")
        request.user = staff
        product_admin = admin.site._registry[Product]
        form = product_admin.get_form(request, obj=self.product)(
            {
                "category": self.product.category_id,
                "name": self.product.name,
                "slug": self.product.slug,
                "sku": self.product.sku,
                "description": self.product.description,
                "short_description": self.product.short_description,
                "base_price": self.product.base_price,
                "currency": self.product.currency,
                "stock_quantity": 10,
                "reorder_level": self.product.reorder_level,
                "status": self.product.status,
                "metadata": "{}",
            },
            instance=self.product,
        )

        self.assertTrue(form.is_valid(), form.errors)
        product_admin.save_model(request, form.instance, form, change=True)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(InventoryAdjustment.objects.get().delta, 7)

    def test_variant_stock_uses_the_same_ledger(self):
        variant = ProductVariant.objects.create(
            product=self.product,
            name="Graphite",
            sku="HEAD-INV-GRAPHITE",
            stock_quantity=1,
        )

        adjustment = adjust_inventory(
            variant=variant,
            delta=2,
            reason=InventoryAdjustment.Reason.RETURNED,
            actor=self.staff,
        )

        variant.refresh_from_db()
        self.assertEqual(variant.stock_quantity, 3)
        self.assertEqual(adjustment.variant, variant)
