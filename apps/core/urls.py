"""Public top-level routes."""

from django.urls import path

from apps.core import views

app_name = "core"

urlpatterns = [
    path("health/", views.health, name="health"),
    path("", views.home, name="home"),
]
