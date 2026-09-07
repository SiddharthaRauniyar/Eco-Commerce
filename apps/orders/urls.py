"""Customer order routes."""

from django.urls import path

from apps.orders import views

app_name = "orders"

urlpatterns = [
    path("", views.order_history, name="history"),
    path("confirmation/<str:order_number>/", views.order_confirmation, name="confirmation"),
    path("<str:order_number>/", views.order_detail, name="detail"),
    path("<str:order_number>/cancel/", views.order_cancel, name="cancel"),
    path("<str:order_number>/return/", views.order_return_request, name="return_request"),
    path("<str:order_number>/refund/", views.order_refund_request, name="refund_request"),
    path("<str:order_number>/reorder/", views.order_reorder, name="reorder"),
    path("<str:order_number>/invoice/", views.order_invoice, name="invoice"),
]
