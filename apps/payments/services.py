"""Small, server-only adapters for hosted Stripe and PayPal checkout."""

import base64
import hashlib
import hmac
import json
import time
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.orders.emails import send_order_confirmation
from apps.orders.models import Order
from apps.orders.services import release_order_inventory
from apps.payments.models import Payment
from apps.security.models import AuditLog


class PaymentGatewayError(ValidationError):
    """A safe, customer-facing payment-provider failure."""


def available_payment_methods() -> list[tuple[str, str]]:
    methods = [(Payment.Provider.CASH_ON_DELIVERY, "Cash on delivery")]
    if settings.STRIPE_SECRET_KEY and settings.STRIPE_WEBHOOK_SECRET:
        methods.append((Payment.Provider.STRIPE, "Card (Stripe)"))
    if settings.PAYPAL_CLIENT_ID and settings.PAYPAL_CLIENT_SECRET and settings.PAYPAL_WEBHOOK_ID:
        methods.append((Payment.Provider.PAYPAL, "PayPal"))
    return methods


def _enabled(provider: str) -> bool:
    return provider in dict(available_payment_methods())


def _request_json(method: str, url: str, *, headers: dict[str, str], body: bytes | None = None) -> dict:
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=settings.PAYMENT_HTTP_TIMEOUT) as response:  # nosec B310: provider URL is settings-owned
            payload = response.read()
    except (HTTPError, URLError, TimeoutError) as error:
        raise PaymentGatewayError("The payment provider is unavailable. Please try again.") from error
    try:
        response_data = json.loads(payload)
    except (TypeError, json.JSONDecodeError) as error:
        raise PaymentGatewayError("The payment provider returned an invalid response.") from error
    if not isinstance(response_data, dict):
        raise PaymentGatewayError("The payment provider returned an invalid response.")
    return response_data


def _post_form(url: str, data: list[tuple[str, str]], *, headers: dict[str, str]) -> dict:
    return _request_json(
        "POST",
        url,
        headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
        body=urlencode(data).encode(),
    )


def _post_json(url: str, data: dict, *, headers: dict[str, str]) -> dict:
    return _request_json(
        "POST",
        url,
        headers={**headers, "Content-Type": "application/json"},
        body=json.dumps(data, separators=(",", ":")).encode(),
    )


def _payment(payment: Payment) -> Payment:
    return Payment.objects.select_related("order__user", "cart").get(pk=payment.pk)


def _save_external_id(payment: Payment, external_id: str, details: dict) -> None:
    with transaction.atomic():
        locked = Payment.objects.select_for_update().get(pk=payment.pk)
        if locked.external_payment_id and locked.external_payment_id != external_id:
            raise PaymentGatewayError("This payment already has a provider reference.")
        locked.external_payment_id = external_id
        locked.raw_event = details
        locked.save(update_fields=("external_payment_id", "raw_event", "updated_at"))


def _minor_units(amount: Decimal, currency: str) -> int:
    # Stripe uses zero-decimal units for these ISO currencies.
    zero_decimal = {"BIF", "CLP", "DJF", "GNF", "JPY", "KMF", "KRW", "MGA", "PYG", "RWF", "UGX", "VND", "VUV", "XAF", "XOF", "XPF"}
    multiplier = Decimal("1") if currency.upper() in zero_decimal else Decimal("100")
    minor = amount * multiplier
    if minor != minor.to_integral_value():
        raise PaymentGatewayError("This payment currency does not support the order amount.")
    return int(minor)


def _amount_from_minor(value, currency: str) -> Decimal:
    zero_decimal = {"BIF", "CLP", "DJF", "GNF", "JPY", "KMF", "KRW", "MGA", "PYG", "RWF", "UGX", "VND", "VUV", "XAF", "XOF", "XPF"}
    multiplier = Decimal("1") if currency.upper() in zero_decimal else Decimal("100")
    return Decimal(str(value)) / multiplier


def create_stripe_checkout(payment: Payment, request) -> str:
    """Create (or safely replay) a Stripe-hosted Checkout Session."""

    if not _enabled(Payment.Provider.STRIPE):
        raise PaymentGatewayError("Card payments are not configured yet.")
    payment = _payment(payment)
    order = payment.order
    success_url = request.build_absolute_uri(reverse("payments:stripe_return"))
    cancel_url = f"{request.build_absolute_uri(reverse('payments:stripe_cancel'))}?payment={payment.pk}"
    data = [
        ("mode", "payment"),
        ("payment_method_types[]", "card"),
        ("success_url", f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}"),
        ("cancel_url", cancel_url),
        ("metadata[order_number]", order.order_number),
        ("payment_intent_data[metadata][order_number]", order.order_number),
        ("line_items[0][price_data][currency]", payment.currency.lower()),
        ("line_items[0][price_data][product_data][name]", f"Order {order.order_number}"),
        ("line_items[0][price_data][unit_amount]", str(_minor_units(payment.amount, payment.currency))),
        ("line_items[0][quantity]", "1"),
    ]
    customer_email = order.guest_email or (order.user.email if order.user else "")
    if customer_email:
        data.append(("customer_email", customer_email))
    credentials = base64.b64encode(f"{settings.STRIPE_SECRET_KEY}:".encode()).decode()
    result = _post_form(
        "https://api.stripe.com/v1/checkout/sessions",
        data,
        headers={"Authorization": f"Basic {credentials}", "Idempotency-Key": payment.idempotency_key},
    )
    session_id, checkout_url = result.get("id"), result.get("url")
    if not isinstance(session_id, str) or not isinstance(checkout_url, str):
        raise PaymentGatewayError("Stripe could not start checkout. Please try again.")
    _save_external_id(payment, session_id, {"checkout_session_id": session_id})
    return checkout_url


def _paypal_token() -> str:
    credentials = base64.b64encode(f"{settings.PAYPAL_CLIENT_ID}:{settings.PAYPAL_CLIENT_SECRET}".encode()).decode()
    result = _post_form(
        f"{settings.PAYPAL_API_BASE}/v1/oauth2/token",
        [("grant_type", "client_credentials")],
        headers={"Authorization": f"Basic {credentials}"},
    )
    token = result.get("access_token")
    if not isinstance(token, str):
        raise PaymentGatewayError("PayPal could not authorize checkout. Please try again.")
    return token


def create_paypal_order(payment: Payment, request) -> str:
    """Create a PayPal order and return its approval URL."""

    if not _enabled(Payment.Provider.PAYPAL):
        raise PaymentGatewayError("PayPal is not configured yet.")
    payment = _payment(payment)
    order = payment.order
    result = _post_json(
        f"{settings.PAYPAL_API_BASE}/v2/checkout/orders",
        {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "reference_id": order.order_number,
                    "custom_id": order.order_number,
                    "amount": {"currency_code": payment.currency, "value": f"{payment.amount:.2f}"},
                }
            ],
            "application_context": {
                "return_url": request.build_absolute_uri(reverse("payments:paypal_return")),
                "cancel_url": request.build_absolute_uri(reverse("payments:paypal_cancel")),
                "user_action": "PAY_NOW",
            },
        },
        headers={"Authorization": f"Bearer {_paypal_token()}", "PayPal-Request-Id": payment.idempotency_key},
    )
    order_id = result.get("id")
    approval_url = next(
        (link.get("href") for link in result.get("links", []) if link.get("rel") in {"payer-action", "approve"}),
        None,
    )
    if not isinstance(order_id, str) or not isinstance(approval_url, str):
        raise PaymentGatewayError("PayPal could not start checkout. Please try again.")
    _save_external_id(payment, order_id, {"paypal_order_id": order_id})
    return approval_url


def _same_amount(value, expected: Decimal) -> bool:
    try:
        return Decimal(str(value)) == expected
    except (InvalidOperation, ValueError):
        return False


@transaction.atomic
def mark_payment_succeeded(payment: Payment, *, provider_reference: str = "", event: dict | None = None) -> Order:
    """Apply a verified completion once, even if the provider retries its webhook."""

    payment = Payment.objects.select_for_update().select_related("order__coupon", "order__user").get(pk=payment.pk)
    if payment.status == Payment.Status.SUCCEEDED:
        return payment.order
    if payment.status in {Payment.Status.FAILED, Payment.Status.CANCELLED, Payment.Status.REFUNDED}:
        return payment.order
    previous_status = payment.status
    payment.status = Payment.Status.SUCCEEDED
    payment.provider_reference = provider_reference[:255]
    payment.paid_at = timezone.now()
    payment.raw_event = event or payment.raw_event
    payment.save(update_fields=("status", "provider_reference", "paid_at", "raw_event", "updated_at"))
    order = payment.order
    order.status = Order.Status.CONFIRMED
    order.payment_status = Order.PaymentStatus.PAID
    order.save(update_fields=("status", "payment_status", "updated_at"))
    if order.user_id and order.coupon_id:
        order.coupon.redeemed_by.add(order.user)
    AuditLog.objects.create(
        action="payment.succeeded",
        target_type="payments.Payment",
        target_id=str(payment.pk),
        before={"status": previous_status},
        after={"status": payment.status, "provider": payment.provider},
    )
    transaction.on_commit(lambda order_id=order.pk: send_order_confirmation(order_id))
    return order


@transaction.atomic
def mark_payment_failed(payment: Payment, *, code: str, message: str, event: dict | None = None) -> Order:
    """Cancel an unpaid attempt once and return its reservation to inventory."""

    payment = Payment.objects.select_for_update().select_related("order", "cart").get(pk=payment.pk)
    if payment.status in {Payment.Status.FAILED, Payment.Status.CANCELLED, Payment.Status.SUCCEEDED, Payment.Status.REFUNDED}:
        return payment.order
    previous_status = payment.status
    payment.status = Payment.Status.FAILED
    payment.failure_code = code[:128]
    payment.failure_message = message[:500]
    payment.raw_event = event or payment.raw_event
    payment.save(update_fields=("status", "failure_code", "failure_message", "raw_event", "updated_at"))
    order = payment.order
    order.status = Order.Status.CANCELLED
    order.payment_status = Order.PaymentStatus.FAILED
    order.save(update_fields=("status", "payment_status", "updated_at"))
    release_order_inventory(order)
    if payment.cart_id and not payment.cart.is_active:
        payment.cart.is_active = True
        payment.cart.save(update_fields=("is_active", "updated_at"))
    AuditLog.objects.create(
        action="payment.failed",
        target_type="payments.Payment",
        target_id=str(payment.pk),
        before={"status": previous_status},
        after={"status": payment.status, "code": payment.failure_code},
    )
    return order


def _stripe_event(payload: bytes, signature: str) -> dict:
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise PaymentGatewayError("Stripe webhook verification is not configured.")
    values: dict[str, list[str]] = {}
    for part in signature.split(","):
        key, separator, value = part.partition("=")
        if separator:
            values.setdefault(key, []).append(value)
    try:
        timestamp = int(values["t"][0])
    except (KeyError, ValueError, IndexError) as error:
        raise PaymentGatewayError("Invalid Stripe webhook signature.") from error
    if abs(int(time.time()) - timestamp) > 300:
        raise PaymentGatewayError("Expired Stripe webhook signature.")
    signed_payload = str(timestamp).encode() + b"." + payload
    expected = hmac.new(settings.STRIPE_WEBHOOK_SECRET.encode(), signed_payload, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, value) for value in values.get("v1", [])):
        raise PaymentGatewayError("Invalid Stripe webhook signature.")
    try:
        event = json.loads(payload)
    except json.JSONDecodeError as error:
        raise PaymentGatewayError("Invalid Stripe webhook payload.") from error
    if not isinstance(event, dict):
        raise PaymentGatewayError("Invalid Stripe webhook payload.")
    return event


def process_stripe_webhook(payload: bytes, signature: str) -> None:
    event = _stripe_event(payload, signature)
    event_type = event.get("type")
    session = event.get("data", {}).get("object", {})
    session_id = session.get("id") if isinstance(session, dict) else None
    if not isinstance(session_id, str):
        return
    payment = Payment.objects.filter(provider=Payment.Provider.STRIPE, external_payment_id=session_id).first()
    if payment is None:
        return
    event_data = {"event_id": event.get("id", ""), "event_type": event_type, "checkout_session_id": session_id}
    if event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"} and session.get("payment_status") == "paid":
        if session.get("currency", "").upper() != payment.currency or not _same_amount(
            _amount_from_minor(session.get("amount_total", -1), payment.currency), payment.amount
        ):
            mark_payment_failed(payment, code="amount_mismatch", message="Stripe payment amount did not match the order.", event=event_data)
            return
        mark_payment_succeeded(payment, provider_reference=str(session.get("payment_intent", "")), event=event_data)
    elif event_type in {"checkout.session.async_payment_failed", "checkout.session.expired"}:
        mark_payment_failed(payment, code="provider_failed", message="Stripe did not complete the payment.", event=event_data)


def _paypal_headers(headers) -> dict[str, str]:
    return {
        "auth_algo": headers.get("PAYPAL-AUTH-ALGO", ""),
        "cert_url": headers.get("PAYPAL-CERT-URL", ""),
        "transmission_id": headers.get("PAYPAL-TRANSMISSION-ID", ""),
        "transmission_sig": headers.get("PAYPAL-TRANSMISSION-SIG", ""),
        "transmission_time": headers.get("PAYPAL-TRANSMISSION-TIME", ""),
    }


def verify_paypal_webhook(headers, event: dict) -> bool:
    if not settings.PAYPAL_WEBHOOK_ID:
        return False
    result = _post_json(
        f"{settings.PAYPAL_API_BASE}/v1/notifications/verify-webhook-signature",
        {**_paypal_headers(headers), "webhook_id": settings.PAYPAL_WEBHOOK_ID, "webhook_event": event},
        headers={"Authorization": f"Bearer {_paypal_token()}"},
    )
    return result.get("verification_status") == "SUCCESS"


def _paypal_payment(event: dict) -> tuple[Payment | None, dict, str]:
    event_type = event.get("event_type", "")
    resource = event.get("resource", {})
    if not isinstance(resource, dict):
        return None, {}, ""
    supplementary_data = resource.get("supplementary_data", {})
    related = supplementary_data.get("related_ids", {}) if isinstance(supplementary_data, dict) else {}
    payment_id = resource.get("id") if event_type.startswith("CHECKOUT.ORDER") else related.get("order_id")
    if not isinstance(payment_id, str):
        return None, resource, event_type
    return Payment.objects.filter(provider=Payment.Provider.PAYPAL, external_payment_id=payment_id).first(), resource, event_type


def _paypal_amount(resource: dict, event_type: str) -> tuple[str, object]:
    if event_type.startswith("CHECKOUT.ORDER"):
        units = resource.get("purchase_units", [])
        amount = units[0].get("amount", {}) if units and isinstance(units[0], dict) else {}
    else:
        amount = resource.get("amount", {})
    if not isinstance(amount, dict):
        return "", ""
    return amount.get("currency_code", ""), amount.get("value", "")


def process_paypal_webhook(event: dict) -> None:
    payment, resource, event_type = _paypal_payment(event)
    if payment is None:
        return
    event_data = {"event_id": event.get("id", ""), "event_type": event_type, "paypal_order_id": payment.external_payment_id}
    if event_type in {"CHECKOUT.ORDER.COMPLETED", "PAYMENT.CAPTURE.COMPLETED"}:
        currency, amount = _paypal_amount(resource, event_type)
        if currency != payment.currency or not _same_amount(amount, payment.amount):
            mark_payment_failed(payment, code="amount_mismatch", message="PayPal payment amount did not match the order.", event=event_data)
            return
        mark_payment_succeeded(payment, provider_reference=str(resource.get("id", "")), event=event_data)
    elif event_type in {"CHECKOUT.ORDER.VOIDED", "PAYMENT.CAPTURE.DENIED"}:
        mark_payment_failed(payment, code="provider_failed", message="PayPal did not complete the payment.", event=event_data)


def capture_paypal_payment(payment: Payment) -> Order:
    """Capture after a buyer returns from PayPal; a verified webhook remains authoritative."""

    payment = _payment(payment)
    if payment.status == Payment.Status.SUCCEEDED:
        return payment.order
    if not payment.external_payment_id:
        raise PaymentGatewayError("PayPal approval could not be found.")
    result = _post_json(
        f"{settings.PAYPAL_API_BASE}/v2/checkout/orders/{payment.external_payment_id}/capture",
        {},
        headers={"Authorization": f"Bearer {_paypal_token()}", "PayPal-Request-Id": payment.idempotency_key},
    )
    if result.get("status") != "COMPLETED":
        raise PaymentGatewayError("PayPal is still confirming this payment.")
    currency, amount = _paypal_amount(result, "CHECKOUT.ORDER.COMPLETED")
    if currency != payment.currency or not _same_amount(amount, payment.amount):
        return mark_payment_failed(payment, code="amount_mismatch", message="PayPal payment amount did not match the order.")
    return mark_payment_succeeded(
        payment,
        provider_reference=str(result.get("id", "")),
        event={"paypal_order_id": payment.external_payment_id, "event_type": "return_capture"},
    )
