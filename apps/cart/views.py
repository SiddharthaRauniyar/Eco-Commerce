"""Customer cart, wishlist, coupon, and initial COD checkout views."""

import secrets

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.cart.forms import AddToCartForm, CheckoutForm, CouponForm
from apps.cart.models import Cart
from apps.cart.services import (
    add_item,
    apply_coupon,
    cart_summary,
    checkout_cash_on_delivery,
    checkout_online_payment,
    clear_coupon,
    current_cart,
    update_item,
)
from apps.payments.models import Payment
from apps.payments.services import create_paypal_order, create_stripe_checkout
from apps.products.models import Product
from apps.wishlist.models import Wishlist


def _message_validation_error(request, error: ValidationError) -> None:
    messages.error(request, error.messages[0])


def cart_detail(request):
    cart = current_cart(request)
    return render(request, "cart/detail.html", {"summary": cart_summary(cart), "coupon_form": CouponForm()})


@require_POST
def cart_add(request, product_id: int):
    product = get_object_or_404(Product, pk=product_id, status=Product.Status.ACTIVE)
    form = AddToCartForm(product, request.POST)
    if form.is_valid():
        try:
            add_item(
                cart=current_cart(request),
                product=product,
                variant=form.cleaned_data.get("variant"),
                quantity=form.cleaned_data["quantity"],
            )
        except ValidationError as error:
            _message_validation_error(request, error)
        else:
            messages.success(request, f"{product.name} is in your cart.")
            return redirect("cart:detail")
    else:
        messages.error(request, form.errors.as_text())
    return redirect("products:detail", slug=product.slug)


@require_POST
def cart_update(request, item_id: int):
    try:
        quantity = int(request.POST.get("quantity", "0"))
        update_item(cart=current_cart(request), item_id=item_id, quantity=quantity)
    except (TypeError, ValueError):
        messages.error(request, "Enter a valid quantity.")
    except ValidationError as error:
        _message_validation_error(request, error)
    else:
        messages.success(request, "Your cart was updated.")
    return redirect("cart:detail")


@require_POST
def cart_remove(request, item_id: int):
    try:
        update_item(cart=current_cart(request), item_id=item_id, quantity=0)
    except ValidationError as error:
        _message_validation_error(request, error)
    else:
        messages.success(request, "Item removed from your cart.")
    return redirect("cart:detail")


@require_POST
def cart_save_for_later(request, item_id: int):
    try:
        cart = current_cart(request)
        item = cart.items.filter(pk=item_id).first()
        if item is None:
            raise ValidationError("This cart item no longer exists.")
        update_item(cart=cart, item_id=item_id, quantity=item.quantity, saved_for_later=True)
    except ValidationError as error:
        _message_validation_error(request, error)
    else:
        messages.success(request, "Item saved for later.")
    return redirect("cart:detail")


@require_POST
def cart_restore(request, item_id: int):
    try:
        cart = current_cart(request)
        item = cart.items.filter(pk=item_id).first()
        if item is None:
            raise ValidationError("This saved item no longer exists.")
        update_item(cart=cart, item_id=item_id, quantity=item.quantity, saved_for_later=False)
    except ValidationError as error:
        _message_validation_error(request, error)
    else:
        messages.success(request, "Item moved back to your cart.")
    return redirect("cart:detail")


@require_POST
def cart_coupon(request):
    cart = current_cart(request)
    code = request.POST.get("code", "").strip()
    if not code:
        clear_coupon(cart=cart)
        messages.success(request, "Coupon removed.")
        return redirect("cart:detail")
    form = CouponForm(request.POST)
    if form.is_valid():
        try:
            apply_coupon(cart=cart, code=form.cleaned_data["code"], user=request.user if request.user.is_authenticated else None)
        except ValidationError as error:
            _message_validation_error(request, error)
        else:
            messages.success(request, "Coupon applied.")
    else:
        messages.error(request, "Enter a coupon code.")
    return redirect("cart:detail")


@login_required
def wishlist_detail(request):
    wishlist, _ = Wishlist.objects.get_or_create(user=request.user)
    return render(request, "wishlist/detail.html", {"wishlist": wishlist, "products": wishlist.products.select_related("category").prefetch_related("images")})


@login_required
@require_POST
def wishlist_add(request, product_id: int):
    product = get_object_or_404(Product, pk=product_id, status=Product.Status.ACTIVE)
    wishlist, _ = Wishlist.objects.get_or_create(user=request.user)
    wishlist.products.add(product)
    messages.success(request, f"{product.name} was saved to your wishlist.")
    return redirect("products:detail", slug=product.slug)


@login_required
@require_POST
def wishlist_remove(request, product_id: int):
    wishlist, _ = Wishlist.objects.get_or_create(user=request.user)
    wishlist.products.remove(product_id)
    messages.success(request, "Item removed from your wishlist.")
    return redirect("wishlist:detail")


def checkout(request):
    if request.method == "GET":
        cart = current_cart(request)
        if not cart.items.filter(saved_for_later=False).exists():
            messages.info(request, "Add an item to your cart before checkout.")
            return redirect("cart:detail")
        initial = {"shipping_method": "standard"}
        if request.user.is_authenticated:
            initial["email"] = request.user.email
        token = secrets.token_urlsafe(32)
        request.session["checkout_token"] = token
        request.session["checkout_cart_id"] = cart.pk
        form = CheckoutForm(initial=initial)
    else:
        token = request.POST.get("checkout_token", "")
        expected_token = request.session.get("checkout_token", "")
        if not token or not secrets.compare_digest(token, expected_token):
            return HttpResponseForbidden("This checkout form has expired. Please start again.")
        cart = Cart.objects.filter(pk=request.session.get("checkout_cart_id")).first() or current_cart(request)
        form = CheckoutForm(request.POST)
        if form.is_valid():
            try:
                if form.cleaned_data["payment_method"] == Payment.Provider.CASH_ON_DELIVERY:
                    order = checkout_cash_on_delivery(
                        cart=cart,
                        data=form.cleaned_data,
                        user=request.user if request.user.is_authenticated else None,
                        idempotency_key=token,
                    )
                    redirect_to = None
                else:
                    payment = checkout_online_payment(
                        cart=cart,
                        data=form.cleaned_data,
                        user=request.user if request.user.is_authenticated else None,
                        idempotency_key=token,
                    )
                    order = payment.order
                    redirect_to = (
                        create_stripe_checkout(payment, request)
                        if payment.provider == Payment.Provider.STRIPE
                        else create_paypal_order(payment, request)
                    )
            except ValidationError as error:
                form.add_error(None, error)
            else:
                request.session.pop("checkout_token", None)
                request.session.pop("checkout_cart_id", None)
                if not request.user.is_authenticated:
                    guest_orders = request.session.get("guest_order_ids", [])
                    request.session["guest_order_ids"] = [*guest_orders, order.pk] if order.pk not in guest_orders else guest_orders
                if redirect_to:
                    return redirect(redirect_to)
                return redirect("orders:confirmation", order_number=order.order_number)
    shipping_method = form.data.get("shipping_method", "standard") if form.is_bound else form.initial["shipping_method"]
    return render(
        request,
        "cart/checkout.html",
        {
            "form": form,
            "summary": cart_summary(cart, shipping_method=shipping_method),
            "checkout_token": request.session.get("checkout_token", ""),
        },
    )
