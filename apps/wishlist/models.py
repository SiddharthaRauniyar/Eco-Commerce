"""Customer wishlist model."""

from django.db import models

from apps.accounts.models import CustomUser
from apps.core.models import TimeStampedModel
from apps.products.models import Product


class Wishlist(TimeStampedModel):
    """Each customer has one wishlist containing any number of products."""

    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="wishlist")
    products = models.ManyToManyField(Product, related_name="wishlists", blank=True)
