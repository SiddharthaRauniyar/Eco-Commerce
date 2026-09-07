"""Security monitoring routes."""

from django.urls import path

from apps.security import views

app_name = "security"

urlpatterns = [
    path("monitoring/", views.SecurityMonitoringView.as_view(), name="monitoring"),
    path("events/<int:event_id>/resolve/", views.resolve_event, name="resolve_event"),
]
