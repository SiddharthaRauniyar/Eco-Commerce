"""Payment attempt history is visible, but provider records are not edited manually."""

from django.contrib import admin

from apps.payments.models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("order", "provider", "status", "amount", "currency", "paid_at", "created_at")
    list_filter = ("provider", "status", "currency", "created_at")
    search_fields = ("order__order_number", "external_payment_id", "provider_reference")
    readonly_fields = (
        "order",
        "provider",
        "status",
        "amount",
        "currency",
        "external_payment_id",
        "idempotency_key",
        "provider_reference",
        "failure_code",
        "failure_message",
        "paid_at",
        "raw_event",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in {"GET", "HEAD"}

    def has_delete_permission(self, request, obj=None):
        return False
