"""Order, line-item, fulfillment, and invoice state models."""

from django.core.validators import MinValueValidator
from django.db import models

from apps.accounts.models import Address, CustomUser
from apps.coupons.models import Coupon
from apps.core.models import TimeStampedModel
from apps.products.models import Product, ProductVariant


class Order(TimeStampedModel):
    """Commercial order with immutable checkout totals and address snapshots."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        PROCESSING = "processing", "Processing"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"
        RETURN_REQUESTED = "return_requested", "Return requested"
        REFUNDED = "refunded", "Refunded"

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        AUTHORIZED = "authorized", "Authorized"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    order_number = models.CharField(max_length=32, unique=True)
    user = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, related_name="orders", null=True, blank=True
    )
    guest_email = models.EmailField(blank=True)
    billing_address = models.ForeignKey(
        Address, on_delete=models.SET_NULL, related_name="billing_orders", null=True, blank=True
    )
    shipping_address = models.ForeignKey(
        Address, on_delete=models.SET_NULL, related_name="shipping_orders", null=True, blank=True
    )
    billing_address_snapshot = models.JSONField(default=dict, blank=True)
    shipping_address_snapshot = models.JSONField(default=dict, blank=True)
    coupon = models.ForeignKey(
        Coupon, on_delete=models.SET_NULL, related_name="orders", null=True, blank=True
    )
    status = models.CharField(max_length=24, choices=Status, default=Status.PENDING)
    payment_status = models.CharField(
        max_length=16, choices=PaymentStatus, default=PaymentStatus.PENDING
    )
    currency = models.CharField(max_length=3, default="USD")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    discount_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    shipping_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    tracking_number = models.CharField(max_length=128, blank=True)
    carrier = models.CharField(max_length=128, blank=True)
    placed_at = models.DateTimeField(auto_now_add=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    invoice_number = models.CharField(max_length=64, unique=True, null=True, blank=True)

    class Meta:
        ordering = ("-placed_at",)
        indexes = [
            models.Index(fields=("user", "status")),
            models.Index(fields=("guest_email", "status")),
        ]

    def __str__(self) -> str:
        return self.order_number


class OrderItem(TimeStampedModel):
    """Immutable product and price snapshot captured when an order is placed."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, related_name="order_items")
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.SET_NULL, null=True, blank=True, related_name="order_items"
    )
    product_name = models.CharField(max_length=255)
    sku = models.CharField(max_length=64)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    line_total = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])

    class Meta:
        indexes = [models.Index(fields=("order", "sku"))]


class OrderRequest(TimeStampedModel):
    """A customer-initiated return or refund request for an existing order."""

    class RequestType(models.TextChoices):
        RETURN = "return", "Return"
        REFUND = "refund", "Refund"

    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        COMPLETED = "completed", "Completed"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="requests")
    user = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, related_name="order_requests", null=True, blank=True
    )
    request_type = models.CharField(max_length=16, choices=RequestType)
    status = models.CharField(max_length=16, choices=Status, default=Status.REQUESTED)
    reason = models.TextField(max_length=2000)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("status", "request_type"))]
        constraints = [
            models.UniqueConstraint(
                fields=("order", "request_type"),
                condition=models.Q(status="requested"),
                name="unique_open_order_request",
            )
        ]

    def __str__(self) -> str:
        return f"{self.order.order_number} - {self.get_request_type_display()}"
