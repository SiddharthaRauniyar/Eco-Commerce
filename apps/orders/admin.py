"""Read-friendly staff administration for completed and pending orders."""

from django.contrib import admin

from apps.orders.models import Order, OrderItem, OrderRequest


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ("product", "variant", "product_name", "sku", "unit_price", "quantity", "line_total")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "customer", "status", "payment_status", "grand_total", "currency", "placed_at")
    list_filter = ("status", "payment_status", "currency", "placed_at")
    search_fields = ("order_number", "user__email", "guest_email", "tracking_number")
    readonly_fields = (
        "order_number",
        "user",
        "guest_email",
        "billing_address_snapshot",
        "shipping_address_snapshot",
        "coupon",
        "currency",
        "subtotal",
        "discount_total",
        "tax_total",
        "shipping_total",
        "grand_total",
        "invoice_number",
        "placed_at",
    )
    list_select_related = ("user",)
    date_hierarchy = "placed_at"
    inlines = (OrderItemInline,)

    @admin.display(description="Customer", ordering="user__email")
    def customer(self, order):
        return order.user or order.guest_email


@admin.register(OrderRequest)
class OrderRequestAdmin(admin.ModelAdmin):
    list_display = ("order", "request_type", "status", "user", "created_at")
    list_filter = ("request_type", "status", "created_at")
    search_fields = ("order__order_number", "user__email", "reason")
    list_select_related = ("order", "user")
    readonly_fields = ("order", "user", "request_type", "reason", "created_at", "updated_at")
