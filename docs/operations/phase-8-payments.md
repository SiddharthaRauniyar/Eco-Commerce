# Phase 8: Payments

Cash on delivery remains enabled by default. Card and PayPal choices appear only after all required server-side values are configured.

| Provider | Required environment variables | Webhook endpoint |
| --- | --- | --- |
| Stripe | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | `/payments/webhooks/stripe/` |
| PayPal | `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_WEBHOOK_ID` | `/payments/webhooks/paypal/` |

Use a public HTTPS URL in live mode. Stripe must send `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `checkout.session.async_payment_failed`, and `checkout.session.expired`. PayPal must send capture-completion and failure events.

The confirmation page does not trust the browser return alone. Stripe completion requires its raw-body HMAC signature; PayPal uses PayPal's verification API. Replayed provider events leave an already completed payment unchanged.

Online checkout reserves inventory for `PAYMENT_RESERVATION_MINUTES` (30 by default). Run this operation on a schedule until the deployment phase adds a worker:

```bash
python3 manage.py expire_pending_payments
```

`PAYPAL_API_BASE` defaults to the PayPal sandbox endpoint. Set it to the live API endpoint only with live credentials. `PAYMENT_HTTP_TIMEOUT` defaults to 10 seconds.
