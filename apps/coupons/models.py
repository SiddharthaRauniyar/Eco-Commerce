"""Discount-rule model used by cart and order services."""

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.accounts.models import CustomUser
from apps.core.models import TimeStampedModel


class Coupon(TimeStampedModel):
    """A time-bounded fixed or percentage discount with optional usage caps."""

    class DiscountType(models.TextChoices):
        PERCENTAGE = "percentage", "Percentage"
        FIXED = "fixed", "Fixed amount"

    code = models.CharField(max_length=64, unique=True)
    discount_type = models.CharField(max_length=16, choices=DiscountType)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    minimum_order_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    per_user_limit = models.PositiveIntegerField(null=True, blank=True)
    redeemed_by = models.ManyToManyField(CustomUser, related_name="redeemed_coupons", blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=("code", "is_active"))]

    def clean(self) -> None:
        super().clean()
        if self.ends_at and self.starts_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "The end time must be after the start time."})
        if self.discount_type == self.DiscountType.PERCENTAGE and self.amount > 100:
            raise ValidationError({"amount": "Percentage discounts cannot exceed 100%."})
