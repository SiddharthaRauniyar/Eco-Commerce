"""Operational coupon administration."""

from django.contrib import admin

from apps.coupons.models import Coupon


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ("code", "discount_type", "amount", "starts_at", "ends_at", "usage_limit", "is_active")
    list_filter = ("discount_type", "is_active", "starts_at", "ends_at")
    list_editable = ("is_active",)
    search_fields = ("code",)
    readonly_fields = ("redeemed_by",)
    date_hierarchy = "ends_at"
