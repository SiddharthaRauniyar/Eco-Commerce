"""Support ticket queue administration."""

from django.contrib import admin

from apps.support.models import SupportTicket


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("subject", "requester", "order", "status", "priority", "assigned_to", "created_at")
    list_filter = ("status", "priority", "created_at")
    list_editable = ("status", "priority", "assigned_to")
    search_fields = ("subject", "message", "requester__email", "order__order_number")
    list_select_related = ("requester", "order", "assigned_to")
    date_hierarchy = "created_at"
