"""Read-only operational queries for the staff dashboard."""

from decimal import Decimal

from django.db.models import F, Sum

from apps.accounts.models import CustomUser
from apps.orders.models import Order, OrderRequest
from apps.products.models import Product, ProductVariant
from apps.reviews.models import Review
from apps.support.models import SupportTicket


def dashboard_data(user) -> dict:
    """Return only metrics the current staff member is permitted to inspect."""

    metrics, low_stock = [], []
    recent_orders = Order.objects.none()
    pending_requests = OrderRequest.objects.none()
    open_tickets = SupportTicket.objects.none()

    if user.has_perm("orders.view_order"):
        paid_revenue = Order.objects.filter(payment_status=Order.PaymentStatus.PAID).aggregate(total=Sum("grand_total"))["total"] or Decimal("0.00")
        metrics.extend(
            [
                {"label": "Paid revenue", "value": f"USD {paid_revenue:,.2f}", "detail": "Completed payments"},
                {"label": "Fulfillment queue", "value": Order.objects.filter(status__in=[Order.Status.CONFIRMED, Order.Status.PROCESSING]).count(), "detail": "Confirmed or processing"},
                {"label": "Open requests", "value": OrderRequest.objects.filter(status=OrderRequest.Status.REQUESTED).count(), "detail": "Returns and refunds"},
            ]
        )
        recent_orders = Order.objects.select_related("user").order_by("-placed_at")[:6]
        pending_requests = OrderRequest.objects.filter(status=OrderRequest.Status.REQUESTED).select_related("order", "user")[:5]

    if user.has_perm("products.view_product"):
        products = Product.objects.filter(stock_quantity__lte=F("reorder_level"))[:5]
        variants = ProductVariant.objects.filter(stock_quantity__lte=F("reorder_level")).select_related("product")[:5]
        low_stock = [
            {"name": product.name, "sku": product.sku, "stock": product.stock_quantity, "reorder_level": product.reorder_level}
            for product in products
        ] + [
            {"name": f"{variant.product.name} - {variant.name}", "sku": variant.sku, "stock": variant.stock_quantity, "reorder_level": variant.reorder_level}
            for variant in variants
        ]
        metrics.append({"label": "Low-stock items", "value": len(low_stock), "detail": "At or below reorder level"})

    if user.has_perm("accounts.view_customuser"):
        metrics.append({"label": "Customers", "value": CustomUser.objects.filter(is_staff=False).count(), "detail": "Registered accounts"})

    if user.has_perm("reviews.view_review"):
        metrics.append({"label": "Reviews to moderate", "value": Review.objects.filter(is_approved=False).count(), "detail": "Awaiting approval"})

    if user.has_perm("support.view_supportticket"):
        open_tickets = SupportTicket.objects.exclude(status__in=[SupportTicket.Status.RESOLVED, SupportTicket.Status.CLOSED]).select_related("requester", "order")[:5]
        metrics.append({"label": "Support queue", "value": open_tickets.count(), "detail": "Open customer conversations"})

    return {
        "metrics": metrics,
        "recent_orders": recent_orders,
        "pending_requests": pending_requests,
        "low_stock": low_stock,
        "open_tickets": open_tickets,
    }
