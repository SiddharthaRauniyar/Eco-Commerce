"""Review moderation administration."""

from django.contrib import admin

from apps.reviews.models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("product", "user", "rating", "is_verified_purchase", "is_approved", "created_at")
    list_filter = ("rating", "is_verified_purchase", "is_approved", "created_at")
    list_editable = ("is_approved",)
    search_fields = ("product__name", "user__email", "title", "body")
    readonly_fields = ("product", "user", "rating", "title", "body", "is_verified_purchase", "created_at", "updated_at")
    list_select_related = ("product", "user", "moderated_by")
    date_hierarchy = "created_at"
