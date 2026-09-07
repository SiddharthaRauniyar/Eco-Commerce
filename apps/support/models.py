"""Customer-support ticket model."""

from django.db import models

from apps.accounts.models import CustomUser
from apps.core.models import TimeStampedModel
from apps.core.validators import validate_support_upload
from apps.orders.models import Order


class SupportTicket(TimeStampedModel):
    """A customer issue with optional order context and staff assignment."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        WAITING_FOR_CUSTOMER = "waiting_for_customer", "Waiting for customer"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    requester = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="support_tickets")
    order = models.ForeignKey(
        Order, on_delete=models.SET_NULL, related_name="support_tickets", null=True, blank=True
    )
    assigned_to = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, related_name="assigned_support_tickets", null=True, blank=True
    )
    subject = models.CharField(max_length=255)
    message = models.TextField()
    status = models.CharField(max_length=24, choices=Status, default=Status.OPEN)
    priority = models.CharField(max_length=16, choices=Priority, default=Priority.NORMAL)
    attachment = models.FileField(upload_to="support-attachments/%Y/%m/", blank=True, validators=[validate_support_upload])
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("status", "priority"))]
