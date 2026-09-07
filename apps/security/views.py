"""Permission-gated views for security monitoring."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from apps.security.dashboard import monitoring_data
from apps.security.models import SecurityEvent
from apps.security.services import resolve_security_event


class SecurityMonitoringView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Show authorized analysts the signals that need attention."""

    template_name = "security/monitoring.html"
    permission_required = "security.view_securityevent"
    raise_exception = True

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), **monitoring_data(self.request.user)}


@require_POST
@login_required
@permission_required("security.change_securityevent", raise_exception=True)
def resolve_event(request, event_id: int):
    """Close a reviewed event without allowing edits to its original evidence."""

    event = get_object_or_404(SecurityEvent, pk=event_id)
    if event.resolved_at:
        messages.info(request, "That security event was already resolved.")
    else:
        resolve_security_event(event, actor=request.user)
        messages.success(request, "Security event marked as resolved.")
    return redirect("security:monitoring")
