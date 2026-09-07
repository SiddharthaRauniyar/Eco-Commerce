"""Public storefront landing page."""

from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

from apps.blog.models import Blog
from apps.categories.models import Category
from apps.orders.models import Order
from apps.products.models import Product
from apps.products.selectors import public_products


def home(request):
    """Render curated catalog slices without duplicating catalog query logic."""

    active_products = public_products()
    best_sellers = list(
        active_products.annotate(
            sales_count=Coalesce(
                Sum(
                    "order_items__quantity",
                    filter=Q(order_items__order__status=Order.Status.DELIVERED),
                ),
                0,
            )
        )
        .order_by("-sales_count", "-created_at")[:4]
    )
    return render(
        request,
        "core/home.html",
        {
            "featured_products": active_products.filter(is_featured=True)[:4],
            "trending_products": active_products.order_by("-updated_at")[:4],
            "best_sellers": best_sellers,
            "new_arrivals": active_products.order_by("-created_at")[:4],
            "categories": Category.objects.filter(is_active=True)
            .annotate(product_count=Count("products", filter=Q(products__status=Product.Status.ACTIVE)))
            .order_by("position", "name")[:6],
            "posts": Blog.objects.filter(status=Blog.Status.PUBLISHED).order_by("-published_at")[:3],
        },
    )


def health(request):
    """Return readiness without disclosing dependency details."""

    try:
        connection.ensure_connection()
        cache.get("health:probe")
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
