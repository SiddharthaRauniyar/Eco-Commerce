"""Explicit state changes used by browser views and future API endpoints."""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import CustomUser, UserProfile
from apps.security.models import LoginAttempt, SecurityEvent


@transaction.atomic
def create_pending_user(form) -> CustomUser:
    """Persist a new account in an inactive state until email verification."""

    user = form.save(commit=False)
    user.is_active = False
    user.save()
    UserProfile.objects.get_or_create(user=user)
    customer_group, _ = Group.objects.get_or_create(name="Customer")
    user.groups.add(customer_group)
    return user


@transaction.atomic
def verify_user_email(user: CustomUser) -> None:
    """Activate a verified user once; replayed links are invalidated by the token."""

    user.is_email_verified = True
    user.is_active = True
    user.save(update_fields=("is_email_verified", "is_active", "updated_at"))
    UserProfile.objects.get_or_create(user=user)


def _request_ip(request) -> str:
    return request.META.get("REMOTE_ADDR") or "0.0.0.0"


def login_is_locked(email: str, request) -> bool:
    """Rate-limit repeated failures by either account identifier or source IP."""

    since = timezone.now() - timedelta(seconds=settings.LOGIN_LOCKOUT_SECONDS)
    criteria = Q(ip_address=_request_ip(request))
    if email:
        criteria |= Q(email=email.lower())
    return LoginAttempt.objects.filter(successful=False, created_at__gte=since).filter(criteria).count() >= settings.LOGIN_FAILURE_LIMIT


def record_login_attempt(
    *, email: str, request, user: CustomUser | None, successful: bool, failure_reason: str = "invalid_credentials"
) -> LoginAttempt:
    """Store a minimal, non-secret audit record for each completed login attempt."""

    # The trusted-proxy middleware replaces REMOTE_ADDR only when the deployment
    # enables its controlled Nginx boundary; otherwise this remains the peer IP.
    attempt = LoginAttempt.objects.create(
        user=user,
        email=email.lower(),
        ip_address=_request_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
        successful=successful,
        failure_reason="" if successful else failure_reason,
    )
    if not successful and login_is_locked(email, request):
        SecurityEvent.objects.create(
            user=user,
            event_type="account.locked",
            severity=SecurityEvent.Severity.HIGH,
            description="Login was temporarily locked after repeated failed attempts.",
            ip_address=_request_ip(request),
        )
    return attempt
