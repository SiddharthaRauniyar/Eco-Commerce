"""Operations dashboard route."""

from django.urls import path

from apps.admin_dashboard.views import OperationsDashboardView, StaffWorkspaceView

app_name = "admin_dashboard"

urlpatterns = [
    path("", OperationsDashboardView.as_view(), name="overview"),
    path("staff/", StaffWorkspaceView.as_view(), name="workspace"),
]
