"""Auditable security telemetry. These records are append-only in services."""

from django.db import models

from apps.accounts.models import CustomUser
from apps.core.models import TimeStampedModel


class ActivityLog(TimeStampedModel):
    """Business-relevant account activity used in customer and staff histories."""

    actor = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, related_name="activity_logs", null=True, blank=True
    )
    action = models.CharField(max_length=128)
    target_type = models.CharField(max_length=100, blank=True)
    target_id = models.CharField(max_length=64, blank=True)
    request_id = models.CharField(max_length=64, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("actor", "created_at")), models.Index(fields=("action", "created_at"))]


class AuditLog(TimeStampedModel):
    """Tamper-evident change record for privileged and sensitive actions."""

    actor = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, related_name="audit_logs", null=True, blank=True
    )
    action = models.CharField(max_length=128)
    target_type = models.CharField(max_length=100)
    target_id = models.CharField(max_length=64)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    request_id = models.CharField(max_length=64, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("target_type", "target_id")), models.Index(fields=("actor", "created_at"))]


class SecurityEvent(TimeStampedModel):
    """A security-relevant signal displayed to authorized analysts."""

    class Severity(models.TextChoices):
        INFO = "info", "Informational"
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    user = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, related_name="security_events", null=True, blank=True
    )
    event_type = models.CharField(max_length=128)
    severity = models.CharField(max_length=16, choices=Severity, default=Severity.INFO)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    request_id = models.CharField(max_length=64, blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, related_name="resolved_security_events", null=True, blank=True
    )

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("severity", "resolved_at")), models.Index(fields=("event_type", "created_at"))]


class LoginAttempt(TimeStampedModel):
    """Every authentication attempt, including unknown email addresses."""

    user = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, related_name="login_attempts", null=True, blank=True
    )
    email = models.EmailField()
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=500, blank=True)
    successful = models.BooleanField(default=False)
    failure_reason = models.CharField(max_length=128, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("email", "created_at")), models.Index(fields=("ip_address", "created_at"))]
