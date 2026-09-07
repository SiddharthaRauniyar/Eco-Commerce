"""Customer wishlist routes."""

from django.urls import path

from apps.cart import views

app_name = "wishlist"

urlpatterns = [
    path("", views.wishlist_detail, name="detail"),
    path("add/<int:product_id>/", views.wishlist_add, name="add"),
    path("remove/<int:product_id>/", views.wishlist_remove, name="remove"),
]
