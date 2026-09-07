"""Customer cart and checkout routes."""

from django.urls import path

from apps.cart import views

app_name = "cart"

urlpatterns = [
    path("", views.cart_detail, name="detail"),
    path("add/<int:product_id>/", views.cart_add, name="add"),
    path("items/<int:item_id>/update/", views.cart_update, name="update"),
    path("items/<int:item_id>/remove/", views.cart_remove, name="remove"),
    path("items/<int:item_id>/save/", views.cart_save_for_later, name="save_for_later"),
    path("items/<int:item_id>/restore/", views.cart_restore, name="restore"),
    path("coupon/", views.cart_coupon, name="coupon"),
    path("checkout/", views.checkout, name="checkout"),
]
