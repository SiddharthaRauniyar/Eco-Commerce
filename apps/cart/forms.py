"""Validation at the cart and checkout trust boundaries."""

from django import forms
from django.core.exceptions import ValidationError

from apps.payments.services import available_payment_methods
from apps.products.models import Product, ProductVariant

from .services import SHIPPING_METHODS


class AddToCartForm(forms.Form):
    variant = forms.ModelChoiceField(queryset=ProductVariant.objects.none(), required=False)
    quantity = forms.IntegerField(min_value=1, initial=1)

    def __init__(self, product: Product, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.product = product
        variants = product.variants.filter(is_active=True).select_related("product")
        self.fields["variant"].queryset = variants
        self._requires_variant = variants.exists()
        if not self._requires_variant:
            self.fields.pop("variant")

    def clean_variant(self):
        variant = self.cleaned_data.get("variant")
        if self._requires_variant and variant is None:
            raise ValidationError("Choose a product variation.")
        return variant


class CouponForm(forms.Form):
    code = forms.CharField(max_length=64)


class CheckoutForm(forms.Form):
    """Addresses are snapshots at checkout; authenticated users may save them."""

    email = forms.EmailField()
    payment_method = forms.ChoiceField(required=False)
    shipping_method = forms.ChoiceField(choices=[(key, label) for key, (label, _) in SHIPPING_METHODS.items()])
    shipping_recipient_name = forms.CharField(max_length=255)
    shipping_line1 = forms.CharField(max_length=255)
    shipping_line2 = forms.CharField(max_length=255, required=False)
    shipping_city = forms.CharField(max_length=128)
    shipping_region = forms.CharField(max_length=128, required=False)
    shipping_postal_code = forms.CharField(max_length=32)
    shipping_country_code = forms.CharField(max_length=2)
    shipping_phone_number = forms.CharField(max_length=32, required=False)
    billing_same_as_shipping = forms.BooleanField(required=False, initial=True)
    billing_recipient_name = forms.CharField(max_length=255, required=False)
    billing_line1 = forms.CharField(max_length=255, required=False)
    billing_line2 = forms.CharField(max_length=255, required=False)
    billing_city = forms.CharField(max_length=128, required=False)
    billing_region = forms.CharField(max_length=128, required=False)
    billing_postal_code = forms.CharField(max_length=32, required=False)
    billing_country_code = forms.CharField(max_length=2, required=False)
    billing_phone_number = forms.CharField(max_length=32, required=False)
    save_address = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["payment_method"].choices = available_payment_methods()

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data["payment_method"] = cleaned_data.get("payment_method") or "cash_on_delivery"
        for prefix in ("shipping", "billing"):
            country = cleaned_data.get(f"{prefix}_country_code")
            if country:
                cleaned_data[f"{prefix}_country_code"] = country.upper()
        if not cleaned_data.get("billing_same_as_shipping"):
            required = ("recipient_name", "line1", "city", "postal_code", "country_code")
            for field in required:
                name = f"billing_{field}"
                if not cleaned_data.get(name):
                    self.add_error(name, "This field is required when billing differs from shipping.")
        return cleaned_data
