"""Release inventory from online payment attempts that outlive their window."""

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.payments.models import Payment
from apps.payments.services import mark_payment_failed


class Command(BaseCommand):
    help = "Cancel expired pending Stripe and PayPal payments and release their reserved stock."

    def handle(self, *args, **options):
        payments = Payment.objects.filter(
            status=Payment.Status.PENDING,
            expires_at__lte=timezone.now(),
        ).exclude(provider=Payment.Provider.CASH_ON_DELIVERY)
        count = 0
        for payment in payments.iterator():
            mark_payment_failed(payment, code="expired", message="The payment reservation expired.")
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Expired {count} payment reservation(s)."))
