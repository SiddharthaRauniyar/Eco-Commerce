"""Staff-only operations overview."""

from django.contrib import admin
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView

from apps.admin_dashboard.services import dashboard_data


class OperationsDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "admin_dashboard/overview.html"

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), **dashboard_data(self.request.user)}


class StaffWorkspaceView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Bring permitted Django-admin tasks into the customer site's navigation."""

    template_name = "admin_dashboard/workspace.html"

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            **dashboard_data(self.request.user),
            "admin_apps": admin.site.get_app_list(self.request),
        }
