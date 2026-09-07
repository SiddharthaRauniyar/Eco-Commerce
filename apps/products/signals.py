"""Invalidate public catalog responses after committed catalog changes."""

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.categories.models import Category
from apps.products.cache import invalidate_catalog_cache
from apps.products.models import Product, ProductAttribute, ProductImage, ProductVariant


@receiver(post_save, sender=Category)
@receiver(post_delete, sender=Category)
@receiver(post_save, sender=Product)
@receiver(post_delete, sender=Product)
@receiver(post_save, sender=ProductImage)
@receiver(post_delete, sender=ProductImage)
@receiver(post_save, sender=ProductVariant)
@receiver(post_delete, sender=ProductVariant)
@receiver(post_save, sender=ProductAttribute)
@receiver(post_delete, sender=ProductAttribute)
def schedule_catalog_cache_invalidation(**kwargs) -> None:
    """A rollback leaves cache keys intact; a commit begins a fresh version."""

    transaction.on_commit(invalidate_catalog_cache)
