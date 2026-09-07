"""Catalog, gallery, variant, and product-specification models."""

from django.core.validators import MinValueValidator
from django.db import models

from apps.categories.models import Category
from apps.core.models import TimeStampedModel
from apps.core.validators import validate_image_upload


class Product(TimeStampedModel):
    """Sellable catalog item; stock is tracked here when no variant is selected."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    sku = models.CharField(max_length=64, unique=True)
    description = models.TextField()
    short_description = models.CharField(max_length=500, blank=True)
    base_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=3, default="USD")
    stock_quantity = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=16, choices=Status, default=Status.DRAFT)
    is_featured = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-is_featured", "name")
        indexes = [models.Index(fields=("status", "category"))]

    def __str__(self) -> str:
        return self.name


class ProductImage(TimeStampedModel):
    """A product-gallery asset; validation is enforced at the upload boundary."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.FileField(upload_to="product-images/%Y/%m/", validators=[validate_image_upload])
    alt_text = models.CharField(max_length=255, blank=True)
    position = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ("position", "id")


class ProductVariant(TimeStampedModel):
    """A purchasable product variation such as colour, size, or storage tier."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=64, unique=True)
    price_override = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    stock_quantity = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=0)
    attributes = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("product", "name")

    def __str__(self) -> str:
        return f"{self.product.name} — {self.name}"


class InventoryAdjustment(models.Model):
    """Immutable record of a deliberate stock change for a product or variant."""

    class Reason(models.TextChoices):
        RECEIVED = "received", "Received stock"
        CORRECTION = "correction", "Stock correction"
        DAMAGED = "damaged", "Damaged or lost"
        RETURNED = "returned", "Customer return"
        RESERVED = "reserved", "Order reservation"
        RELEASED = "released", "Reservation release"

    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="inventory_adjustments", null=True, blank=True
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.PROTECT,
        related_name="inventory_adjustments",
        null=True,
        blank=True,
    )
    delta = models.IntegerField()
    reason = models.CharField(max_length=16, choices=Reason)
    note = models.CharField(max_length=500, blank=True)
    actor = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.SET_NULL,
        related_name="inventory_adjustments",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(product__isnull=False, variant__isnull=True)
                    | models.Q(product__isnull=True, variant__isnull=False)
                ),
                name="inventory_adjustment_one_stock_target",
            ),
            models.CheckConstraint(condition=~models.Q(delta=0), name="inventory_adjustment_nonzero_delta"),
        ]
        indexes = [models.Index(fields=("created_at",)), models.Index(fields=("reason", "created_at"))]

    def clean(self) -> None:
        super().clean()
        if bool(self.product_id) == bool(self.variant_id):
            from django.core.exceptions import ValidationError

            raise ValidationError("Choose exactly one product or product variant.")

    def __str__(self) -> str:
        target = self.variant or self.product
        return f"{target}: {self.delta:+d}"


class ProductAttribute(TimeStampedModel):
    """A displayable product specification such as material or dimensions."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="attributes")
    name = models.CharField(max_length=100)
    value = models.CharField(max_length=255)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("position", "name")
        constraints = [models.UniqueConstraint(fields=("product", "name"), name="unique_product_attribute")]
