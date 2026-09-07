"""Read-only, permission-aware aggregates for staff reporting."""

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, F, Sum
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.orders.models import Order, OrderItem
from apps.products.models import Product, ProductVariant
from apps.security.models import SecurityEvent

REPORT_WINDOWS = {7, 30, 90}


def report_window(value) -> int:
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = 30
    return value if value in REPORT_WINDOWS else 30


def _period_rows(queryset, truncator, label_format: str) -> list[dict]:
    return [
        {
            "period": row["period"],
            "label": row["period"].strftime(label_format),
            "orders": row["orders"],
            "revenue": row["revenue"] or Decimal("0.00"),
        }
        for row in queryset.annotate(period=truncator("placed_at")).values("period").annotate(
            orders=Count("id"), revenue=Sum("grand_total")
        ).order_by("period")
    ]


def report_data(user, days: int) -> dict:
    """Build the selected reporting window without exposing unpermitted data."""

    days = report_window(days)
    end = timezone.localdate()
    start = end - timedelta(days=days - 1)
    paid_orders = Order.objects.filter(
        payment_status=Order.PaymentStatus.PAID,
        placed_at__date__range=(start, end),
    )
    can_orders = user.has_perm("orders.view_order")
    can_products = user.has_perm("products.view_product")
    can_coupons = user.has_perm("coupons.view_coupon")
    can_customers = user.has_perm("accounts.view_customuser")
    can_security = user.has_perm("security.view_securityevent")
    summary, daily, weekly, monthly, products, coupons = [], [], [], [], [], []

    if can_orders:
        total = paid_orders.aggregate(total=Sum("grand_total"))["total"] or Decimal("0.00")
        count = paid_orders.count()
        summary.extend(
            [
                {"label": "Paid revenue", "value": f"USD {total:,.2f}"},
                {"label": "Paid orders", "value": count},
                {"label": "Average order", "value": f"USD {(total / count if count else Decimal('0.00')):,.2f}"},
            ]
        )
        grouped_days = paid_orders.annotate(period=TruncDate("placed_at")).values("period").annotate(
            orders=Count("id"), revenue=Sum("grand_total")
        )
        grouped = {row["period"]: row for row in grouped_days}
        daily = [
            {
                "period": start + timedelta(days=index),
                "label": (start + timedelta(days=index)).strftime("%d %b"),
                "orders": grouped.get(start + timedelta(days=index), {}).get("orders", 0),
                "revenue": grouped.get(start + timedelta(days=index), {}).get("revenue", Decimal("0.00")) or Decimal("0.00"),
            }
            for index in range(days)
        ]
        weekly = _period_rows(paid_orders, TruncWeek, "Week of %d %b")
        monthly = _period_rows(paid_orders, TruncMonth, "%b %Y")
        products = list(
            OrderItem.objects.filter(order__in=paid_orders)
            .values("product_name", "sku")
            .annotate(units_sold=Sum("quantity"), revenue=Sum("line_total"))
            .order_by("-revenue", "product_name")[:10]
        )

    if can_customers:
        summary.append(
            {
                "label": "New customers",
                "value": CustomUser.objects.filter(created_at__date__range=(start, end), is_staff=False).count(),
            }
        )

    inventory = []
    if can_products:
        inventory = [
            {"name": product.name, "sku": product.sku, "stock": product.stock_quantity, "reorder_level": product.reorder_level}
            for product in Product.objects.filter(stock_quantity__lte=F("reorder_level")).order_by("stock_quantity", "name")[:10]
        ] + [
            {"name": f"{variant.product.name} - {variant.name}", "sku": variant.sku, "stock": variant.stock_quantity, "reorder_level": variant.reorder_level}
            for variant in ProductVariant.objects.filter(stock_quantity__lte=F("reorder_level")).select_related("product").order_by("stock_quantity", "name")[:10]
        ]
        summary.append({"label": "Low-stock items", "value": len(inventory)})

    if can_coupons and can_orders:
        coupons = list(
            paid_orders.filter(coupon__isnull=False)
            .values("coupon__code")
            .annotate(orders=Count("id"), discount_total=Sum("discount_total"))
            .order_by("-discount_total", "coupon__code")[:10]
        )

    security = []
    if can_security:
        security = list(
            SecurityEvent.objects.filter(created_at__date__range=(start, end))
            .values("severity")
            .annotate(events=Count("id"))
            .order_by("severity")
        )

    return {
        "days": days,
        "start": start,
        "end": end,
        "summary": summary,
        "daily": daily,
        "weekly": weekly,
        "monthly": monthly,
        "products": products,
        "inventory": inventory,
        "coupons": coupons,
        "security": security,
        "can_orders": can_orders,
        "can_products": can_products,
        "can_coupons": can_coupons,
        "can_security": can_security,
    }
