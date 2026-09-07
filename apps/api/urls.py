"""Stable version-one API routes."""

from django.urls import path

from apps.api import views

app_name = "api"

urlpatterns = [
    path("auth/token/", views.SecureTokenObtainPairView.as_view(), name="token"),
    path("auth/token/refresh/", views.PublicTokenRefreshView.as_view(), name="token-refresh"),
    path("auth/token/revoke/", views.PublicTokenRevokeView.as_view(), name="token-revoke"),
    path("categories/", views.CategoryListView.as_view(), name="category-list"),
    path("products/", views.ProductListView.as_view(), name="product-list"),
    path("products/<slug:slug>/", views.ProductDetailView.as_view(), name="product-detail"),
    path("me/", views.MeView.as_view(), name="me"),
    path("addresses/", views.AddressListCreateView.as_view(), name="address-list"),
    path("addresses/<int:pk>/", views.AddressDetailView.as_view(), name="address-detail"),
    path("wishlist/", views.WishlistView.as_view(), name="wishlist"),
    path("wishlist/products/<slug:slug>/", views.WishlistProductView.as_view(), name="wishlist-product"),
    path("orders/", views.OrderListView.as_view(), name="order-list"),
    path("orders/<str:order_number>/", views.OrderDetailView.as_view(), name="order-detail"),
    path("orders/<str:order_number>/cancel/", views.OrderCancelView.as_view(), name="order-cancel"),
    path("orders/<str:order_number>/return/", views.OrderReturnView.as_view(), name="order-return"),
    path("orders/<str:order_number>/refund/", views.OrderRefundView.as_view(), name="order-refund"),
]
