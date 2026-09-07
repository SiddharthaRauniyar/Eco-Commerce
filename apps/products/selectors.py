"""Reusable, read-only catalog queries for pages and future API endpoints."""

from django.db.models import QuerySet
from django.db.models import Q

from apps.products.models import Product

SORTS = {
    "newest": ("-created_at",),
    "price_low": ("base_price", "name"),
    "price_high": ("-base_price", "name"),
    "name": ("name",),
}


def public_products(
    *,
    query: str = "",
    category_slug: str = "",
    sort: str = "newest",
    include_images: bool = True,
    include_variants: bool = False,
    include_attributes: bool = False,
) -> QuerySet[Product]:
    """Return active products with only the public relations each caller needs."""

    prefetches = []
    if include_images:
        prefetches.append("images")
    if include_variants:
        prefetches.append("variants")
    if include_attributes:
        prefetches.append("attributes")

    products = Product.objects.filter(
        status=Product.Status.ACTIVE, category__is_active=True
    ).select_related("category")
    if prefetches:
        products = products.prefetch_related(*prefetches)
    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(description__icontains=query) | Q(sku__icontains=query)
        )
    if category_slug:
        products = products.filter(category__slug=category_slug)
    return products.order_by(*SORTS.get(sort, SORTS["newest"]))
