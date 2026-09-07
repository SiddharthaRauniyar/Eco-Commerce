"""Transactional customer order actions shared by browser views and future APIs."""

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.cart.models import Cart
from apps.cart.services import add_item
from apps.orders.models import Order, OrderRequest
from apps.products.models import InventoryAdjustment
from apps.products.services import adjust_inventory
from apps.security.models import AuditLog


def _audit(action: str, order: Order, user, **after) -> None:
    AuditLog.objects.create(
        actor=user,
        action=action,
        target_type="orders.Order",
        target_id=str(order.pk),
        before={},
        after=after,
    )


def release_order_inventory(order: Order) -> None:
    """Return a cancelled order's reservation to inventory once per transition."""

    for item in order.items.select_related("product", "variant"):
        if item.variant_id:
            adjust_inventory(
                variant=item.variant,
                delta=item.quantity,
                reason=InventoryAdjustment.Reason.RELEASED,
                note=f"Released for {order.order_number}",
            )
        elif item.product_id:
            adjust_inventory(
                product=item.product,
                delta=item.quantity,
                reason=InventoryAdjustment.Reason.RELEASED,
                note=f"Released for {order.order_number}",
            )


def _create_request(order: Order, user, request_type: str, reason: str) -> OrderRequest:
    if OrderRequest.objects.filter(
        order=order, request_type=request_type, status=OrderRequest.Status.REQUESTED
    ).exists():
        raise ValidationError("You already have an open request of this type for this order.")
    request = OrderRequest.objects.create(
        order=order, user=user, request_type=request_type, reason=reason.strip()
    )
    _audit("order.requested", order, user, request_type=request_type, request_id=request.pk)
    return request


@transaction.atomic
def cancel_order(order: Order, *, user) -> Order:
    """Cancel an unfulfilled order, restore stock, and request a refund when needed."""

    order = Order.objects.select_for_update().get(pk=order.pk, user=user)
    if order.status != Order.Status.CONFIRMED:
        raise ValidationError("Only confirmed, unfulfilled orders can be cancelled.")
    order.status = Order.Status.CANCELLED
    order.save(update_fields=("status", "updated_at"))
    release_order_inventory(order)
    if order.payment_status == Order.PaymentStatus.PAID:
        _create_request(order, user, OrderRequest.RequestType.REFUND, "Cancelled before fulfillment.")
    _audit("order.cancelled", order, user, status=order.status)
    return order


@transaction.atomic
def request_return(order: Order, *, user, reason: str) -> OrderRequest:
    """Request a return only after an order has been delivered."""

    order = Order.objects.select_for_update().get(pk=order.pk, user=user)
    if order.status != Order.Status.DELIVERED:
        raise ValidationError("Returns can be requested after delivery.")
    request = _create_request(order, user, OrderRequest.RequestType.RETURN, reason)
    order.status = Order.Status.RETURN_REQUESTED
    order.save(update_fields=("status", "updated_at"))
    return request


@transaction.atomic
def request_refund(order: Order, *, user, reason: str) -> OrderRequest:
    """Record a paid-order refund request for staff review."""

    order = Order.objects.select_for_update().get(pk=order.pk, user=user)
    if order.payment_status != Order.PaymentStatus.PAID:
        raise ValidationError("Only paid orders can have a refund request.")
    if order.status not in {Order.Status.CANCELLED, Order.Status.DELIVERED, Order.Status.RETURN_REQUESTED}:
        raise ValidationError("Refund requests are available after cancellation, delivery, or a return request.")
    return _create_request(order, user, OrderRequest.RequestType.REFUND, reason)


@transaction.atomic
def reorder_order(order: Order, *, user) -> Cart:
    """Add every still-available line from a prior order to the active customer cart."""

    order = Order.objects.select_for_update().prefetch_related("items__product", "items__variant").get(
        pk=order.pk, user=user
    )
    cart = Cart.objects.select_for_update().filter(user=user, is_active=True).order_by("-updated_at").first()
    cart = cart or Cart.objects.create(user=user)
    for item in order.items.all():
        if item.product_id is None:
            raise ValidationError(f"{item.product_name} is no longer available.")
        add_item(cart=cart, product=item.product, variant=item.variant, quantity=item.quantity)
    _audit("order.reordered", order, user, cart_id=cart.pk)
    return cart
