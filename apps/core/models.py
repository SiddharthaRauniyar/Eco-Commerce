"""Shared model primitives used by domain applications."""

from django.db import models


class TimeStampedModel(models.Model):
    """Adds immutable creation and automatic modification timestamps."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
