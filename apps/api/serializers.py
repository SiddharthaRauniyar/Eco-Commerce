"""Explicit public API shapes and the MFA-aware JWT sign-in serializer."""

from django.contrib.auth import authenticate
from rest_framework import serializers, status
from rest_framework.exceptions import APIException, AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.accounts.mfa import decrypt_totp_secret, verify_totp
from apps.accounts.models import Address, CustomUser, UserProfile
from apps.accounts.services import login_is_locked, record_login_attempt
from apps.orders.models import Order, OrderItem, OrderRequest
from apps.products.models import Product, ProductAttribute, ProductImage, ProductVariant


class LoginLocked(APIException):
    """Return a throttling response after the shared login lockout triggers."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Too many sign-in attempts. Please try again later."
    default_code = "login_locked"


class SecureTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Issue JWTs only after the project's lockout and MFA checks succeed."""

    mfa_code = serializers.CharField(required=False, write_only=True, trim_whitespace=True, max_length=6)

    def _fail(self, *, email: str, user: CustomUser | None, reason: str) -> None:
        request = self.context["request"]
        record_login_attempt(
            email=email,
            request=request,
            user=user,
            successful=False,
            failure_reason=reason,
        )
        if login_is_locked(email, request):
            raise LoginLocked()
        raise AuthenticationFailed("Unable to authenticate.")

    def validate(self, attrs):
        request = self.context["request"]
        email = str(attrs[self.username_field]).strip().lower()
        if login_is_locked(email, request):
            raise LoginLocked()

        user = authenticate(request=request, email=email, password=attrs["password"])
        known_user = CustomUser.objects.filter(email__iexact=email).first()
        if user is None:
            self._fail(email=email, user=known_user, reason="invalid_credentials")

        self.user = user
        if not user.is_email_verified:
            self._fail(email=email, user=user, reason="email_unverified")

        profile, _ = UserProfile.objects.get_or_create(user=user)
        if profile.mfa_enabled:
            try:
                secret = decrypt_totp_secret(profile)
            except ValueError:
                self._fail(email=email, user=user, reason="mfa_unavailable")
            if not verify_totp(secret, attrs.get("mfa_code", "")):
                self._fail(email=email, user=user, reason="invalid_mfa_code")

        record_login_attempt(email=email, request=request, user=user, successful=True)
        refresh = self.get_token(user)
        return {"refresh": str(refresh), "access": str(refresh.access_token)}


def _file_url(file_field, request):
    """Expose a public media URL, never the storage field or backend key."""

    if not file_field:
        return None
    try:
        url = file_field.url
    except ValueError:
        return None
    return request.build_absolute_uri(url) if request else url


class CategorySerializer(serializers.Serializer):
    name = serializers.CharField(read_only=True)
    slug = serializers.SlugField(read_only=True)
    description = serializers.CharField(read_only=True)


class ProductImageSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ("url", "alt_text")

    def get_url(self, image):
        return _file_url(image.image, self.context.get("request"))


class ProductAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductAttribute
        fields = ("name", "value")


class ProductVariantSerializer(serializers.ModelSerializer):
    in_stock = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = ("name", "price_override", "attributes", "in_stock")

    def get_in_stock(self, variant) -> bool:
        return variant.stock_quantity > 0


class ProductListSerializer(serializers.ModelSerializer):
    category = serializers.SlugRelatedField(read_only=True, slug_field="slug")
    image_url = serializers.SerializerMethodField()
    in_stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "name",
            "slug",
            "short_description",
            "base_price",
            "currency",
            "is_featured",
            "category",
            "image_url",
            "in_stock",
        )

    def get_image_url(self, product):
        primary = next((image for image in product.images.all() if image.is_primary), None)
        image = primary or next(iter(product.images.all()), None)
        return _file_url(image.image, self.context.get("request")) if image else None

    def get_in_stock(self, product) -> bool:
        active_variants = [variant for variant in product.variants.all() if variant.is_active]
        return any(variant.stock_quantity > 0 for variant in active_variants) if active_variants else product.stock_quantity > 0


class ProductDetailSerializer(ProductListSerializer):
    description = serializers.CharField(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    variants = serializers.SerializerMethodField()
    attributes = ProductAttributeSerializer(many=True, read_only=True)

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + ("description", "images", "variants", "attributes")

    def get_variants(self, product):
        variants = [variant for variant in product.variants.all() if variant.is_active]
        return ProductVariantSerializer(variants, many=True, context=self.context).data


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ("email", "first_name", "last_name", "is_email_verified")
        read_only_fields = ("email", "is_email_verified")


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = (
            "id",
            "label",
            "recipient_name",
            "line1",
            "line2",
            "city",
            "region",
            "postal_code",
            "country_code",
            "phone_number",
            "is_default_shipping",
            "is_default_billing",
        )
        read_only_fields = ("id",)

    def validate_country_code(self, value: str) -> str:
        value = value.strip().upper()
        if len(value) != 2 or not value.isalpha():
            raise serializers.ValidationError("Use a two-letter country code.")
        return value


class WishlistProductSerializer(serializers.Serializer):
    product_slug = serializers.SlugField()


class WishlistSerializer(serializers.Serializer):
    products = ProductListSerializer(many=True, read_only=True)


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ("product_name", "sku", "unit_price", "quantity", "line_total")


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "order_number",
            "status",
            "payment_status",
            "currency",
            "subtotal",
            "discount_total",
            "tax_total",
            "shipping_total",
            "grand_total",
            "tracking_number",
            "carrier",
            "placed_at",
            "items",
        )


class OrderRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderRequest
        fields = ("request_type", "status", "reason", "created_at")


class OrderReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=2000, trim_whitespace=True)
