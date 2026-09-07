"""Read-oriented administration for security evidence and audit records."""

from django.contrib import admin

from apps.security.models import ActivityLog, AuditLog, LoginAttempt, SecurityEvent
from apps.security.services import resolve_security_event


class ReadOnlySecurityAdmin(admin.ModelAdmin):
    readonly_fields = ()

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ActivityLog)
class ActivityLogAdmin(ReadOnlySecurityAdmin):
    list_display = ("action", "actor", "target_type", "target_id", "ip_address", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("action", "actor__email", "target_type", "target_id", "ip_address")
    list_select_related = ("actor",)
    readonly_fields = ("actor", "action", "target_type", "target_id", "request_id", "ip_address", "user_agent", "metadata", "created_at", "updated_at")


@admin.register(AuditLog)
class AuditLogAdmin(ReadOnlySecurityAdmin):
    list_display = ("action", "actor", "target_type", "target_id", "ip_address", "created_at")
    list_filter = ("action", "target_type", "created_at")
    search_fields = ("action", "actor__email", "target_type", "target_id", "ip_address")
    list_select_related = ("actor",)
    readonly_fields = ("actor", "action", "target_type", "target_id", "before", "after", "request_id", "ip_address", "created_at", "updated_at")


@admin.register(LoginAttempt)
class LoginAttemptAdmin(ReadOnlySecurityAdmin):
    list_display = ("email", "successful", "failure_reason", "ip_address", "created_at")
    list_filter = ("successful", "failure_reason", "created_at")
    search_fields = ("email", "ip_address", "user__email")
    list_select_related = ("user",)
    readonly_fields = ("user", "email", "ip_address", "user_agent", "successful", "failure_reason", "created_at", "updated_at")


@admin.register(SecurityEvent)
class SecurityEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "severity", "user", "ip_address", "resolved_at", "created_at")
    list_filter = ("severity", "resolved_at", "event_type", "created_at")
    search_fields = ("event_type", "description", "user__email", "ip_address", "request_id")
    list_select_related = ("user", "resolved_by")
    readonly_fields = ("user", "event_type", "severity", "description", "ip_address", "request_id", "evidence", "resolved_at", "resolved_by", "created_at", "updated_at")
    actions = ("resolve_selected",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Mark selected events as resolved")
    def resolve_selected(self, request, queryset):
        resolved = 0
        for event in queryset.filter(resolved_at__isnull=True):
            resolve_security_event(event, actor=request.user)
            resolved += 1
        self.message_user(request, f"Resolved {resolved} security event(s).")
