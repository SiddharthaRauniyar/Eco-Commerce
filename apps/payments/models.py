"""Payment-attempt records; provider secrets and card data are never stored here."""

from django.db import models
from django.db.models import Q

from apps.cart.models import Cart
from apps.core.models import TimeStampedModel
from apps.orders.models import Order


class Payment(TimeStampedModel):
    """A traceable provider payment attempt for one order."""

    class Provider(models.TextChoices):
        STRIPE = "stripe", "Stripe"
        PAYPAL = "paypal", "PayPal"
        CASH_ON_DELIVERY = "cash_on_delivery", "Cash on delivery"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        AUTHORIZED = "authorized", "Authorized"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="payments")
    cart = models.ForeignKey(
        Cart, on_delete=models.SET_NULL, related_name="payment_attempts", null=True, blank=True
    )
    provider = models.CharField(max_length=32, choices=Provider)
    status = models.CharField(max_length=16, choices=Status, default=Status.PENDING)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    external_payment_id = models.CharField(max_length=255, blank=True)
    idempotency_key = models.CharField(max_length=255, unique=True)
    provider_reference = models.CharField(max_length=255, blank=True)
    failure_code = models.CharField(max_length=128, blank=True)
    failure_message = models.CharField(max_length=500, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    raw_event = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=("provider", "external_payment_id")), models.Index(fields=("status",))]
        constraints = [
            models.UniqueConstraint(
                fields=("provider", "external_payment_id"),
                condition=~Q(external_payment_id=""),
                name="unique_provider_external_payment",
            )
        ]
