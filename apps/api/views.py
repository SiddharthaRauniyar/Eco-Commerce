"""DRF endpoints that expose only public catalog data and owned customer data."""

from hashlib import sha256

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenBlacklistView, TokenObtainPairView, TokenRefreshView

from apps.accounts.models import Address
from apps.categories.models import Category
from apps.orders.models import Order
from apps.orders.services import cancel_order, request_refund, request_return
from apps.products.cache import catalog_cache_version
from apps.products.models import Product
from apps.products.selectors import SORTS, public_products
from apps.wishlist.models import Wishlist
from apps.api.serializers import (
    AccountSerializer,
    AddressSerializer,
    CategorySerializer,
    LoginLocked,
    OrderReasonSerializer,
    OrderRequestSerializer,
    OrderSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    SecureTokenObtainPairSerializer,
    WishlistProductSerializer,
    WishlistSerializer,
)


class SecureTokenObtainPairView(TokenObtainPairView):
    serializer_class = SecureTokenObtainPairSerializer
    permission_classes = (permissions.AllowAny,)

    def handle_exception(self, exc):
        response = super().handle_exception(exc)
        if isinstance(exc, LoginLocked):
            response["Retry-After"] = str(settings.LOGIN_LOCKOUT_SECONDS)
        return response


class PublicTokenRefreshView(TokenRefreshView):
    permission_classes = (permissions.AllowAny,)


class PublicTokenRevokeView(TokenBlacklistView):
    permission_classes = (permissions.AllowAny,)


class PublicCatalogCacheMixin:
    """Cache only unpersonalized, unfiltered public API reads."""

    def _cache_key(self, request):
        if not settings.PUBLIC_API_CACHE_SECONDS or request.query_params:
            return None
        identity = f"{request.scheme}|{request.get_host()}|{request.path}"
        return f"api:catalog:v{catalog_cache_version()}:{sha256(identity.encode()).hexdigest()}"

    def get(self, request, *args, **kwargs):
        key = self._cache_key(request)
        if key is None:
            return super().get(request, *args, **kwargs)

        data = cache.get(key)
        if data is None:
            response = super().get(request, *args, **kwargs)
            if response.status_code == status.HTTP_200_OK:
                cache.set(key, response.data, settings.PUBLIC_API_CACHE_SECONDS)
        else:
            response = Response(data)
        response["Cache-Control"] = f"public, max-age={settings.PUBLIC_API_CACHE_SECONDS}"
        return response


class CategoryListView(PublicCatalogCacheMixin, generics.ListAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = CategorySerializer
    queryset = Category.objects.filter(is_active=True).order_by("position", "name")
    pagination_class = None


class ProductListView(PublicCatalogCacheMixin, generics.ListAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = ProductListSerializer

    def get_queryset(self):
        query = self.request.query_params.get("q", "").strip()[:100]
        category_slug = self.request.query_params.get("category", "").strip()[:120]
        sort = self.request.query_params.get("sort", "newest")
        return public_products(
            query=query,
            category_slug=category_slug,
            sort=sort if sort in SORTS else "newest",
            include_variants=True,
        )


class ProductDetailView(PublicCatalogCacheMixin, generics.RetrieveAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = ProductDetailSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return public_products(include_variants=True, include_attributes=True)


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = AccountSerializer

    def get_object(self):
        return self.request.user


class AddressListCreateView(generics.ListCreateAPIView):
    serializer_class = AddressSerializer

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AddressSerializer

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)


class WishlistView(APIView):
    def _response(self, request, *, status_code=status.HTTP_200_OK):
        products = public_products(include_variants=True).filter(wishlists__user=request.user)
        return Response(
            WishlistSerializer({"products": products}, context={"request": request}).data,
            status=status_code,
        )

    def get(self, request):
        return self._response(request)

    def post(self, request):
        serializer = WishlistProductSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = get_object_or_404(
            Product.objects.filter(status=Product.Status.ACTIVE, category__is_active=True).only("pk"),
            slug=serializer.validated_data["product_slug"],
        )
        wishlist, _ = Wishlist.objects.get_or_create(user=request.user)
        already_saved = wishlist.products.filter(pk=product.pk).exists()
        wishlist.products.add(product)
        return self._response(
            request,
            status_code=status.HTTP_200_OK if already_saved else status.HTTP_201_CREATED,
        )


class WishlistProductView(APIView):
    def delete(self, request, slug):
        wishlist = get_object_or_404(Wishlist, user=request.user)
        product = get_object_or_404(wishlist.products, slug=slug)
        wishlist.products.remove(product)
        return Response(status=status.HTTP_204_NO_CONTENT)


def _owned_order(request, order_number):
    return get_object_or_404(
        Order.objects.filter(user=request.user).prefetch_related("items"), order_number=order_number
    )


def _validation_error(error):
    return Response({"detail": error.messages[0]}, status=status.HTTP_400_BAD_REQUEST)


class OrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related("items")


class OrderDetailView(generics.RetrieveAPIView):
    serializer_class = OrderSerializer
    lookup_field = "order_number"

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related("items")


class OrderCancelView(APIView):
    def post(self, request, order_number):
        order = _owned_order(request, order_number)
        try:
            order = cancel_order(order, user=request.user)
        except ValidationError as error:
            return _validation_error(error)
        return Response(OrderSerializer(order, context={"request": request}).data)


class OrderReturnView(APIView):
    def post(self, request, order_number):
        payload = OrderReasonSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        order = _owned_order(request, order_number)
        try:
            order_request = request_return(order, user=request.user, reason=payload.validated_data["reason"])
        except ValidationError as error:
            return _validation_error(error)
        return Response(
            OrderRequestSerializer(order_request).data,
            status=status.HTTP_201_CREATED,
        )


class OrderRefundView(APIView):
    def post(self, request, order_number):
        payload = OrderReasonSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        order = _owned_order(request, order_number)
        try:
            order_request = request_refund(order, user=request.user, reason=payload.validated_data["reason"])
        except ValidationError as error:
            return _validation_error(error)
        return Response(
            OrderRequestSerializer(order_request).data,
            status=status.HTTP_201_CREATED,
        )
