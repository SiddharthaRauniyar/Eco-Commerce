"""Customer product-review and moderation model."""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.accounts.models import CustomUser
from apps.core.models import TimeStampedModel
from apps.products.models import Product


class Review(TimeStampedModel):
    """One review per customer/product pair, publishable only after moderation."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    title = models.CharField(max_length=255, blank=True)
    body = models.TextField()
    is_verified_purchase = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    moderated_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, related_name="moderated_reviews", null=True, blank=True
    )
    moderated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("product", "user"), name="unique_product_review")]
        ordering = ("-created_at",)
