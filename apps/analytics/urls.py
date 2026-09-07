"""Staff reporting routes."""

from django.urls import path

from apps.analytics import views

app_name = "analytics"

urlpatterns = [
    path("", views.ReportsView.as_view(), name="reports"),
    path("export/<str:file_format>/", views.report_export, name="export"),
]
