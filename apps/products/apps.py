"""Application configuration for catalog cache invalidation hooks."""

from django.apps import AppConfig


class ProductsConfig(AppConfig):
    name = "apps.products"

    def ready(self):
        from apps.products import signals  # noqa: F401
