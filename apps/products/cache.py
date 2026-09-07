"""Tiny versioned cache helper for public catalog responses."""

from django.core.cache import cache

CATALOG_CACHE_VERSION_KEY = "catalog:version"


def catalog_cache_version() -> int:
    return cache.get_or_set(CATALOG_CACHE_VERSION_KEY, 1, timeout=None)


def invalidate_catalog_cache() -> None:
    """Move new requests to fresh keys without needing a cache-wide delete."""

    try:
        cache.incr(CATALOG_CACHE_VERSION_KEY)
    except ValueError:
        cache.set(CATALOG_CACHE_VERSION_KEY, 2, timeout=None)
