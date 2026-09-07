"""Read-only queries for the permission-scoped security monitoring dashboard."""

from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from apps.security.models import ActivityLog, AuditLog, LoginAttempt, SecurityEvent


def monitoring_data(user) -> dict:
    """Return only the security records the current user may inspect."""

    since = timezone.now() - timedelta(hours=24)
    can_events = user.has_perm("security.view_securityevent")
    can_logins = user.has_perm("security.view_loginattempt")
    can_audit = user.has_perm("security.view_auditlog")
    can_activity = user.has_perm("security.view_activitylog")
    open_events = SecurityEvent.objects.none()
    recent_logins = LoginAttempt.objects.none()
    recent_audits = AuditLog.objects.none()
    recent_activity = ActivityLog.objects.none()
    metrics = []

    if can_events:
        open_events = SecurityEvent.objects.filter(resolved_at__isnull=True).select_related("user")[:12]
        metrics.extend(
            [
                {
                    "label": "Critical open events",
                    "value": SecurityEvent.objects.filter(
                        resolved_at__isnull=True, severity=SecurityEvent.Severity.CRITICAL
                    ).count(),
                    "detail": "Require immediate review",
                },
                {
                    "label": "Open high-risk events",
                    "value": SecurityEvent.objects.filter(
                        resolved_at__isnull=True, severity=SecurityEvent.Severity.HIGH
                    ).count(),
                    "detail": "Awaiting investigation",
                },
                {
                    "label": "Signals in 24 hours",
                    "value": SecurityEvent.objects.filter(created_at__gte=since).count(),
                    "detail": "All recorded severities",
                },
            ]
        )

    if can_logins:
        recent_logins = LoginAttempt.objects.filter(successful=False)[:10]
        metrics.append(
            {
                "label": "Failed sign-ins in 24 hours",
                "value": LoginAttempt.objects.filter(successful=False, created_at__gte=since).count(),
                "detail": "By email or source address",
            }
        )

    if can_audit:
        recent_audits = AuditLog.objects.select_related("actor")[:10]
    if can_activity:
        recent_activity = ActivityLog.objects.select_related("actor")[:10]

    return {
        "metrics": metrics,
        "open_events": open_events,
        "recent_logins": recent_logins,
        "recent_audits": recent_audits,
        "recent_activity": recent_activity,
        "can_resolve_events": user.has_perm("security.change_securityevent"),
        "event_breakdown": (
            SecurityEvent.objects.filter(created_at__gte=since)
            .values("severity")
            .annotate(events=Count("id"))
            .order_by("severity")
            if can_events
            else []
        ),
    }
