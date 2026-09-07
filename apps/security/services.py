"""Small, auditable state changes for the security monitoring workspace."""

from django.db import transaction
from django.utils import timezone

from apps.security.models import AuditLog, SecurityEvent


@transaction.atomic
def resolve_security_event(event: SecurityEvent, *, actor) -> SecurityEvent:
    """Resolve an open event once and record who made the decision."""

    event = SecurityEvent.objects.select_for_update().get(pk=event.pk)
    if event.resolved_at:
        return event
    event.resolved_at = timezone.now()
    event.resolved_by = actor
    event.save(update_fields=("resolved_at", "resolved_by", "updated_at"))
    AuditLog.objects.create(
        actor=actor,
        action="security.event_resolved",
        target_type="security.SecurityEvent",
        target_id=str(event.pk),
        after={"severity": event.severity, "event_type": event.event_type},
    )
    return event
