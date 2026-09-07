"""Anonymous and authenticated shopping cart models."""

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from apps.accounts.models import CustomUser
from apps.coupons.models import Coupon
from apps.core.models import TimeStampedModel
from apps.products.models import Product, ProductVariant


class Cart(TimeStampedModel):
    """One cart belongs either to a customer or to an anonymous session."""

    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="carts", null=True, blank=True
    )
    session_key = models.CharField(max_length=40, unique=True, null=True, blank=True)
    coupon = models.ForeignKey(
        Coupon, on_delete=models.SET_NULL, related_name="carts", null=True, blank=True
    )
    currency = models.CharField(max_length=3, default="USD")
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=("user", "is_active"))]


class CartItem(TimeStampedModel):
    """A cart line that points to a product or a specific product variant."""

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="cart_items")
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.PROTECT, related_name="cart_items", null=True, blank=True
    )
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    saved_for_later = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("cart", "product"),
                condition=Q(variant__isnull=True),
                name="unique_cart_product_without_variant",
            ),
            models.UniqueConstraint(
                fields=("cart", "variant"),
                condition=Q(variant__isnull=False),
                name="unique_cart_variant",
            ),
        ]
