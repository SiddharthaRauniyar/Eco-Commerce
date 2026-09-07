"""Plain-text transactional emails for confirmed customer orders."""

import logging

from django.core.mail import send_mail
from django.template.loader import render_to_string

from apps.orders.models import Order

logger = logging.getLogger(__name__)


def send_order_confirmation(order_id: int) -> None:
    """Email the immutable order snapshot after its transaction commits."""

    order = Order.objects.select_related("user").prefetch_related("items").filter(pk=order_id).first()
    if not order:
        return
    recipient = order.user.email if order.user_id else order.guest_email
    if not recipient:
        return
    try:
        send_mail(
            f"Your Secure Commerce order {order.order_number}",
            render_to_string("orders/email_confirmation.txt", {"order": order}),
            None,
            [recipient],
        )
    except Exception:
        logger.exception("Could not send confirmation for order %s", order.order_number)
