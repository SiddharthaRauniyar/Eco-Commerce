"""Admin-site behavior that stays independent from storefront sign-out."""

from django.contrib.admin.apps import AdminConfig
from django.contrib.admin.sites import AdminSite
from django.http import HttpResponseNotAllowed, HttpResponseRedirect
from django.urls import reverse


_ADMIN_AUTHENTICATION_KEY = "secure_commerce_admin_user_id"


class StorefrontPreservingAdminSite(AdminSite):
    """Require a separate admin gate without flushing the storefront session."""

    def has_permission(self, request):
        return (
            super().has_permission(request)
            and request.session.get(_ADMIN_AUTHENTICATION_KEY) == str(request.user.pk)
        )

    def login(self, request, extra_context=None):
        response = super().login(request, extra_context=extra_context)
        if request.method == "POST" and 300 <= response.status_code < 400 and request.user.is_staff:
            request.session[_ADMIN_AUTHENTICATION_KEY] = str(request.user.pk)
        return response

    def logout(self, request, extra_context=None):
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        # ponytail: one browser identity; add a separate admin cookie only for concurrent accounts.
        request.session.pop(_ADMIN_AUTHENTICATION_KEY, None)
        return HttpResponseRedirect(reverse("admin:login", current_app=self.name))


class SecureCommerceAdminConfig(AdminConfig):
    default_site = "config.admin.StorefrontPreservingAdminSite"
