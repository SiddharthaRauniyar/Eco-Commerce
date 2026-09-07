"""SEO-aware editorial content model."""

from django.db import models

from apps.accounts.models import CustomUser
from apps.core.models import TimeStampedModel


class Blog(TimeStampedModel):
    """Published article with editorial ownership and search metadata."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    author = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name="blog_posts")
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    excerpt = models.TextField(blank=True)
    body = models.TextField()
    status = models.CharField(max_length=16, choices=Status, default=Status.DRAFT)
    seo_title = models.CharField(max_length=255, blank=True)
    seo_description = models.CharField(max_length=320, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-published_at", "-created_at")
        indexes = [models.Index(fields=("status", "published_at"))]
