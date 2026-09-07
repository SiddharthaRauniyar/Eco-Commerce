"""Return and webhook endpoints for server-verified payment completion."""

import json

from django.contrib import messages
from django.http import Http404, HttpResponse, HttpResponseBadRequest, HttpResponseServerError
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from apps.payments.models import Payment
from apps.payments.services import (
    PaymentGatewayError,
    capture_paypal_payment,
    mark_payment_failed,
    process_paypal_webhook,
    process_stripe_webhook,
    verify_paypal_webhook,
)


def _can_view_payment(request, payment: Payment) -> bool:
    order = payment.order
    return (request.user.is_authenticated and order.user_id == request.user.id) or (
        not order.user_id and order.pk in request.session.get("guest_order_ids", [])
    )


def _payment_or_404(request, *, provider: str, external_id: str = "", payment_id: str = "") -> Payment:
    filters = {"provider": provider}
    if external_id:
        filters["external_payment_id"] = external_id
    elif payment_id.isdigit():
        filters["pk"] = int(payment_id)
    else:
        raise Http404
    payment = Payment.objects.select_related("order").filter(**filters).first()
    if payment is None or not _can_view_payment(request, payment):
        raise Http404
    return payment


@require_GET
def stripe_return(request):
    payment = _payment_or_404(request, provider=Payment.Provider.STRIPE, external_id=request.GET.get("session_id", ""))
    messages.info(request, "Your card payment is being confirmed. This page updates after Stripe's verified notification.")
    return redirect("orders:confirmation", order_number=payment.order.order_number)


@require_GET
def stripe_cancel(request):
    payment = _payment_or_404(request, provider=Payment.Provider.STRIPE, payment_id=request.GET.get("payment", ""))
    mark_payment_failed(payment, code="cancelled", message="Customer cancelled Stripe checkout.")
    messages.info(request, "Card checkout was cancelled. Your reserved items are back in the cart.")
    return redirect("cart:checkout")


@require_GET
def paypal_return(request):
    payment = _payment_or_404(request, provider=Payment.Provider.PAYPAL, external_id=request.GET.get("token", ""))
    try:
        capture_paypal_payment(payment)
    except PaymentGatewayError:
        messages.info(request, "PayPal is still confirming this payment. Please check the order again shortly.")
    return redirect("orders:confirmation", order_number=payment.order.order_number)


@require_GET
def paypal_cancel(request):
    payment = _payment_or_404(request, provider=Payment.Provider.PAYPAL, external_id=request.GET.get("token", ""))
    mark_payment_failed(payment, code="cancelled", message="Customer cancelled PayPal checkout.")
    messages.info(request, "PayPal checkout was cancelled. Your reserved items are back in the cart.")
    return redirect("cart:checkout")


@csrf_exempt
@require_POST
def stripe_webhook(request):
    try:
        process_stripe_webhook(request.body, request.headers.get("Stripe-Signature", ""))
    except PaymentGatewayError:
        return HttpResponseBadRequest()
    return HttpResponse(status=204)


@csrf_exempt
@require_POST
def paypal_webhook(request):
    try:
        event = json.loads(request.body)
        if not isinstance(event, dict) or not verify_paypal_webhook(request.headers, event):
            return HttpResponseBadRequest()
        process_paypal_webhook(event)
    except json.JSONDecodeError:
        return HttpResponseBadRequest()
    except PaymentGatewayError:
        return HttpResponseServerError()
    return HttpResponse(status=204)
