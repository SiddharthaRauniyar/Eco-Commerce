"""Editorial publishing administration."""

from django.contrib import admin

from apps.blog.models import Blog


@admin.register(Blog)
class BlogAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "status", "published_at", "updated_at")
    list_filter = ("status", "published_at")
    list_editable = ("status",)
    search_fields = ("title", "excerpt", "body", "author__email")
    prepopulated_fields = {"slug": ("title",)}
    list_select_related = ("author",)
    date_hierarchy = "published_at"
