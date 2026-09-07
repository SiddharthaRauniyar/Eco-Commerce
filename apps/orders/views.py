"""Customer order history, tracking, requests, reordering, and invoices."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.orders.forms import OrderRequestForm
from apps.orders.invoices import ensure_invoice_number, render_invoice
from apps.orders.models import Order
from apps.orders.services import cancel_order, reorder_order, request_refund, request_return


def order_confirmation(request, order_number: str):
    """Show a confirmation to the order owner or the guest checkout session."""

    order = Order.objects.select_related("user").filter(order_number=order_number).first()
    if order is None:
        raise Http404
    is_owner = request.user.is_authenticated and order.user_id == request.user.id
    is_guest_checkout = not order.user_id and order.pk in request.session.get("guest_order_ids", [])
    if not is_owner and not is_guest_checkout:
        raise Http404
    return render(request, "orders/confirmation.html", {"order": order})


def _customer_order(request, order_number: str) -> Order:
    return get_object_or_404(
        Order.objects.select_related("user").prefetch_related("items", "requests"),
        order_number=order_number,
        user=request.user,
    )


@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).annotate(item_count=Count("items"))
    return render(request, "orders/history.html", {"orders": orders})


@login_required
def order_detail(request, order_number: str):
    order = _customer_order(request, order_number)
    return render(
        request,
        "orders/detail.html",
        {
            "order": order,
            "return_form": OrderRequestForm(prefix="return"),
            "refund_form": OrderRequestForm(prefix="refund"),
            "can_cancel": order.status == Order.Status.CONFIRMED,
            "can_return": order.status == Order.Status.DELIVERED,
            "can_refund": order.payment_status == Order.PaymentStatus.PAID
            and order.status in {Order.Status.CANCELLED, Order.Status.DELIVERED, Order.Status.RETURN_REQUESTED},
        },
    )


@login_required
@require_POST
def order_cancel(request, order_number: str):
    order = _customer_order(request, order_number)
    try:
        cancel_order(order, user=request.user)
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        messages.success(request, "Order cancelled. Stock has been released.")
    return redirect("orders:detail", order_number=order.order_number)


@login_required
@require_POST
def order_return_request(request, order_number: str):
    order = _customer_order(request, order_number)
    form = OrderRequestForm(request.POST, prefix="return")
    if form.is_valid():
        try:
            request_return(order, user=request.user, reason=form.cleaned_data["reason"])
        except ValidationError as error:
            messages.error(request, error.messages[0])
        else:
            messages.success(request, "Return request submitted for review.")
    else:
        messages.error(request, "Please include a reason for the return request.")
    return redirect("orders:detail", order_number=order.order_number)


@login_required
@require_POST
def order_refund_request(request, order_number: str):
    order = _customer_order(request, order_number)
    form = OrderRequestForm(request.POST, prefix="refund")
    if form.is_valid():
        try:
            request_refund(order, user=request.user, reason=form.cleaned_data["reason"])
        except ValidationError as error:
            messages.error(request, error.messages[0])
        else:
            messages.success(request, "Refund request submitted for review.")
    else:
        messages.error(request, "Please include a reason for the refund request.")
    return redirect("orders:detail", order_number=order.order_number)


@login_required
@require_POST
def order_reorder(request, order_number: str):
    order = _customer_order(request, order_number)
    try:
        reorder_order(order, user=request.user)
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return redirect("orders:detail", order_number=order.order_number)
    messages.success(request, "Available items were added to your cart at their current price.")
    return redirect("cart:detail")


@login_required
def order_invoice(request, order_number: str):
    order = _customer_order(request, order_number)
    if order.status == Order.Status.PENDING:
        raise Http404
    order = ensure_invoice_number(order)
    response = HttpResponse(render_invoice(order), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{order.invoice_number}.pdf"'
    return response
