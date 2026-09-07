"""Payment return and webhook routes."""

from django.urls import path

from apps.payments import views

app_name = "payments"

urlpatterns = [
    path("stripe/return/", views.stripe_return, name="stripe_return"),
    path("stripe/cancel/", views.stripe_cancel, name="stripe_cancel"),
    path("paypal/return/", views.paypal_return, name="paypal_return"),
    path("paypal/cancel/", views.paypal_cancel, name="paypal_cancel"),
    path("webhooks/stripe/", views.stripe_webhook, name="stripe_webhook"),
    path("webhooks/paypal/", views.paypal_webhook, name="paypal_webhook"),
]
