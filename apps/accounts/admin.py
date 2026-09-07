"""Django-admin integration for account and address administration."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.accounts.models import Address, CustomUser, UserProfile


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "is_email_verified", "is_staff", "is_active")
    list_filter = ("is_staff", "is_superuser", "is_active", "is_email_verified", "groups")
    search_fields = ("email", "first_name", "last_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal information", {"fields": ("first_name", "last_name")}),
        ("Verification", {"fields": ("is_email_verified",)}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "first_name", "last_name", "password1", "password2")}),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "mfa_enabled", "newsletter_opt_in", "marketing_opt_in", "updated_at")
    search_fields = ("user__email",)
    exclude = ("mfa_secret_encrypted",)
    list_select_related = ("user",)


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("recipient_name", "user", "city", "country_code", "is_default_shipping")
    list_filter = ("country_code", "is_default_shipping", "is_default_billing")
    search_fields = ("recipient_name", "user__email", "city", "postal_code")
    list_select_related = ("user",)
