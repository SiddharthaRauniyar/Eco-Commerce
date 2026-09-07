"""Catalog taxonomy models."""

from django.db import models

from apps.core.models import TimeStampedModel


class Category(TimeStampedModel):
    """Hierarchical product category with a stable public slug."""

    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, related_name="children", null=True, blank=True
    )
    is_active = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("position", "name")

    def __str__(self) -> str:
        return self.name
