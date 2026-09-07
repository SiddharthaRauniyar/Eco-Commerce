"""Small customer-facing forms for order management actions."""

from django import forms


class OrderRequestForm(forms.Form):
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={"rows": 4}))
