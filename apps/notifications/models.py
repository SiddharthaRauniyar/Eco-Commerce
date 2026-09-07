"""In-app notification records and delivery preferences."""

from django.db import models

from apps.accounts.models import CustomUser
from apps.core.models import TimeStampedModel


class Notification(TimeStampedModel):
    """A user-addressed notification with a safe navigation target."""

    class Channel(models.TextChoices):
        IN_APP = "in_app", "In-app"
        EMAIL = "email", "Email"
        PUSH = "push", "Push"

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="notifications")
    channel = models.CharField(max_length=16, choices=Channel, default=Channel.IN_APP)
    title = models.CharField(max_length=255)
    body = models.TextField()
    action_url = models.CharField(max_length=500, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("user", "read_at"))]
