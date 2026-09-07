"""Cart, coupon, pricing, and cash-on-delivery checkout workflows."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Address, CustomUser
from apps.cart.models import Cart, CartItem
from apps.coupons.models import Coupon
from apps.orders.emails import send_order_confirmation
from apps.orders.models import Order, OrderItem
from apps.payments.models import Payment
from apps.products.models import InventoryAdjustment, Product, ProductVariant
from apps.products.services import adjust_inventory

MONEY_PLACES = Decimal("0.01")
SHIPPING_METHODS = {
    "standard": ("Standard delivery", Decimal("10.00")),
    "express": ("Express delivery", Decimal("25.00")),
}


@dataclass(slots=True)
class CartLine:
    item: CartItem
    unit_price: Decimal
    line_total: Decimal


@dataclass(slots=True)
class CartSummary:
    cart: Cart
    lines: list[CartLine]
    saved_items: list[CartItem]
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    shipping_total: Decimal
    grand_total: Decimal
    coupon_error: str = ""


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


def _line_price(item: CartItem) -> Decimal:
    if item.variant and item.variant.price_override is not None:
        return item.variant.price_override
    return item.product.base_price


def _stock_target(product: Product, variant: ProductVariant | None):
    return variant or product


def _get_or_create_user_cart(user: CustomUser) -> Cart:
    cart = Cart.objects.filter(user=user, is_active=True).order_by("-updated_at").first()
    return cart or Cart.objects.create(user=user)


@transaction.atomic
def current_cart(request) -> Cart:
    """Return the active cart, merging an anonymous cart on first signed-in use."""

    if not request.session.session_key:
        request.session.create()
    guest_cart = Cart.objects.filter(session_key=request.session.session_key, is_active=True).first()
    if not request.user.is_authenticated:
        return guest_cart or Cart.objects.create(session_key=request.session.session_key)

    user_cart = _get_or_create_user_cart(request.user)
    if not guest_cart or guest_cart.pk == user_cart.pk:
        return user_cart

    for item in guest_cart.items.select_related("product", "variant"):
        add_item(user_cart, product=item.product, variant=item.variant, quantity=item.quantity)
    if guest_cart.coupon and not user_cart.coupon:
        user_cart.coupon = guest_cart.coupon
        user_cart.save(update_fields=("coupon", "updated_at"))
    guest_cart.is_active = False
    guest_cart.save(update_fields=("is_active", "updated_at"))
    return user_cart


@transaction.atomic
def add_item(*, cart: Cart, product: Product, variant: ProductVariant | None, quantity: int) -> CartItem:
    """Add available active stock to a cart without reserving it yet."""

    if quantity < 1:
        raise ValidationError("Quantity must be at least one.")
    product = Product.objects.select_for_update().get(pk=product.pk, status=Product.Status.ACTIVE)
    if variant is not None:
        variant = ProductVariant.objects.select_for_update().get(pk=variant.pk, product=product, is_active=True)
    elif product.variants.filter(is_active=True).exists():
        raise ValidationError("Choose a product variation before adding this item.")

    has_existing_items = CartItem.objects.filter(cart=cart).exists()
    if has_existing_items and cart.currency != product.currency:
        raise ValidationError("Your cart can contain products in only one currency.")
    if not has_existing_items and cart.currency != product.currency:
        cart.currency = product.currency
        cart.save(update_fields=("currency", "updated_at"))

    target = _stock_target(product, variant)
    item, _ = CartItem.objects.select_for_update().get_or_create(
        cart=cart, product=product, variant=variant, defaults={"quantity": 0}
    )
    requested_quantity = item.quantity + quantity
    if requested_quantity > target.stock_quantity:
        raise ValidationError("The requested quantity is not available.")
    item.quantity = requested_quantity
    item.saved_for_later = False
    item.save(update_fields=("quantity", "saved_for_later", "updated_at"))
    return item


@transaction.atomic
def update_item(*, cart: Cart, item_id: int, quantity: int, saved_for_later: bool | None = None) -> CartItem | None:
    """Update a cart line, removing it when the requested quantity is zero."""

    item = CartItem.objects.select_related("product", "variant").select_for_update().filter(cart=cart, pk=item_id).first()
    if item is None:
        raise ValidationError("This cart item no longer exists.")
    if quantity <= 0:
        item.delete()
        return None
    target = _stock_target(item.product, item.variant)
    if quantity > target.stock_quantity:
        raise ValidationError("The requested quantity is not available.")
    item.quantity = quantity
    if saved_for_later is not None:
        item.saved_for_later = saved_for_later
    item.save(update_fields=("quantity", "saved_for_later", "updated_at"))
    return item


def _validate_coupon(coupon: Coupon, *, subtotal: Decimal, user: CustomUser | None) -> None:
    now = timezone.now()
    if not coupon.is_active or coupon.starts_at > now or coupon.ends_at <= now:
        raise ValidationError("This coupon is not currently valid.")
    if subtotal < coupon.minimum_order_amount:
        raise ValidationError(f"This coupon requires an order of at least {coupon.minimum_order_amount}.")
    completed_orders = coupon.orders.exclude(status=Order.Status.CANCELLED)
    if coupon.usage_limit is not None and completed_orders.count() >= coupon.usage_limit:
        raise ValidationError("This coupon has reached its usage limit.")
    if user and coupon.per_user_limit is not None and completed_orders.filter(user=user).count() >= coupon.per_user_limit:
        raise ValidationError("You have reached the usage limit for this coupon.")


def _discount(coupon: Coupon | None, *, subtotal: Decimal, user: CustomUser | None) -> Decimal:
    if coupon is None:
        return Decimal("0.00")
    _validate_coupon(coupon, subtotal=subtotal, user=user)
    if coupon.discount_type == Coupon.DiscountType.PERCENTAGE:
        return _money(min(subtotal, subtotal * coupon.amount / Decimal("100")))
    return _money(min(subtotal, coupon.amount))


@transaction.atomic
def apply_coupon(*, cart: Cart, code: str, user: CustomUser | None) -> Coupon:
    """Validate and attach a coupon; redemption occurs only after checkout."""

    coupon = Coupon.objects.select_for_update().filter(code__iexact=code.strip()).first()
    if coupon is None:
        raise ValidationError("That coupon code was not found.")
    subtotal = sum(
        (_line_price(item) * item.quantity for item in cart.items.select_related("product", "variant").filter(saved_for_later=False)),
        start=Decimal("0.00"),
    )
    _validate_coupon(coupon, subtotal=subtotal, user=user)
    cart.coupon = coupon
    cart.save(update_fields=("coupon", "updated_at"))
    return coupon


@transaction.atomic
def clear_coupon(*, cart: Cart) -> None:
    cart.coupon = None
    cart.save(update_fields=("coupon", "updated_at"))


def cart_summary(cart: Cart, *, shipping_method: str | None = None, strict_coupon: bool = False) -> CartSummary:
    """Compute a server-side cart total; never trust browser-provided prices."""

    items = list(cart.items.select_related("product", "variant").filter(saved_for_later=False))
    saved_items = list(cart.items.select_related("product", "variant").filter(saved_for_later=True))
    lines = [CartLine(item=item, unit_price=_line_price(item), line_total=_money(_line_price(item) * item.quantity)) for item in items]
    subtotal = sum((line.line_total for line in lines), start=Decimal("0.00"))
    coupon_error = ""
    try:
        discount_total = _discount(cart.coupon, subtotal=subtotal, user=cart.user)
    except ValidationError as error:
        if strict_coupon:
            raise
        discount_total = Decimal("0.00")
        coupon_error = error.messages[0]
    shipping_total = SHIPPING_METHODS.get(shipping_method, ("", Decimal("0.00")))[1]
    taxable_total = max(subtotal - discount_total, Decimal("0.00"))
    tax_total = _money(taxable_total * settings.CHECKOUT_TAX_RATE)
    return CartSummary(
        cart=cart,
        lines=lines,
        saved_items=saved_items,
        subtotal=_money(subtotal),
        discount_total=discount_total,
        tax_total=tax_total,
        shipping_total=shipping_total,
        grand_total=_money(taxable_total + tax_total + shipping_total),
        coupon_error=coupon_error,
    )


def _address_snapshot(data: dict, prefix: str) -> dict[str, str]:
    return {
        "recipient_name": data[f"{prefix}_recipient_name"],
        "line1": data[f"{prefix}_line1"],
        "line2": data.get(f"{prefix}_line2", ""),
        "city": data[f"{prefix}_city"],
        "region": data.get(f"{prefix}_region", ""),
        "postal_code": data[f"{prefix}_postal_code"],
        "country_code": data[f"{prefix}_country_code"].upper(),
        "phone_number": data.get(f"{prefix}_phone_number", ""),
    }


def _save_address(user: CustomUser, snapshot: dict[str, str], *, label: str) -> Address:
    return Address.objects.create(user=user, label=label, **snapshot)


@transaction.atomic
def _checkout(*, cart: Cart, data: dict, user: CustomUser | None, idempotency_key: str, provider: str) -> Payment:
    """Create one stock-reserved checkout attempt; the token makes retries safe."""

    existing_payment = Payment.objects.select_related("order").filter(idempotency_key=idempotency_key).first()
    if existing_payment:
        if existing_payment.provider != provider:
            raise ValidationError("This checkout was already started with another payment method.")
        return existing_payment

    locked_cart = Cart.objects.select_for_update().select_related("coupon").get(pk=cart.pk, is_active=True)
    summary = cart_summary(locked_cart, shipping_method=data["shipping_method"], strict_coupon=True)
    if not summary.lines:
        raise ValidationError("Your cart is empty.")

    shipping_snapshot = _address_snapshot(data, "shipping")
    billing_snapshot = shipping_snapshot if data["billing_same_as_shipping"] else _address_snapshot(data, "billing")
    shipping_address = billing_address = None
    if user and data.get("save_address"):
        shipping_address = _save_address(user, shipping_snapshot, label="Checkout shipping")
        billing_address = shipping_address if data["billing_same_as_shipping"] else _save_address(
            user, billing_snapshot, label="Checkout billing"
        )

    order = Order.objects.create(
        order_number=f"SC-{uuid4().hex[:12].upper()}",
        user=user,
        guest_email="" if user else data["email"],
        billing_address=billing_address,
        shipping_address=shipping_address,
        billing_address_snapshot=billing_snapshot,
        shipping_address_snapshot=shipping_snapshot,
        coupon=locked_cart.coupon,
        currency=locked_cart.currency,
        subtotal=summary.subtotal,
        discount_total=summary.discount_total,
        tax_total=summary.tax_total,
        shipping_total=summary.shipping_total,
        grand_total=summary.grand_total,
        status=Order.Status.CONFIRMED if provider == Payment.Provider.CASH_ON_DELIVERY else Order.Status.PENDING,
    )
    for line in summary.lines:
        adjust_inventory(
            product=line.item.product if line.item.variant is None else None,
            variant=line.item.variant,
            delta=-line.item.quantity,
            reason=InventoryAdjustment.Reason.RESERVED,
            actor=user,
            note=f"Reserved for {order.order_number}",
        )
        OrderItem.objects.create(
            order=order,
            product=line.item.product,
            variant=line.item.variant,
            product_name=line.item.product.name,
            sku=line.item.variant.sku if line.item.variant else line.item.product.sku,
            unit_price=line.unit_price,
            quantity=line.item.quantity,
            line_total=line.line_total,
        )
    payment = Payment.objects.create(
        order=order,
        cart=locked_cart,
        provider=provider,
        amount=order.grand_total,
        currency=order.currency,
        idempotency_key=idempotency_key,
        expires_at=(
            None
            if provider == Payment.Provider.CASH_ON_DELIVERY
            else timezone.now() + timedelta(minutes=settings.PAYMENT_RESERVATION_MINUTES)
        ),
    )
    if provider == Payment.Provider.CASH_ON_DELIVERY and user and locked_cart.coupon:
        locked_cart.coupon.redeemed_by.add(user)
    locked_cart.is_active = False
    locked_cart.save(update_fields=("is_active", "updated_at"))
    if provider == Payment.Provider.CASH_ON_DELIVERY:
        transaction.on_commit(lambda order_id=order.pk: send_order_confirmation(order_id))
    return payment


def checkout_cash_on_delivery(*, cart: Cart, data: dict, user: CustomUser | None, idempotency_key: str) -> Order:
    """Create a confirmed cash-on-delivery order."""

    return _checkout(
        cart=cart,
        data=data,
        user=user,
        idempotency_key=idempotency_key,
        provider=Payment.Provider.CASH_ON_DELIVERY,
    ).order


def checkout_online_payment(*, cart: Cart, data: dict, user: CustomUser | None, idempotency_key: str) -> Payment:
    """Create a pending online-payment order and reserve its stock."""

    return _checkout(
        cart=cart,
        data=data,
        user=user,
        idempotency_key=idempotency_key,
        provider=data["payment_method"],
    )
