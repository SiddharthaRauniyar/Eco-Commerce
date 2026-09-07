"""Server-side validation for browser authentication flows."""

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError

from apps.accounts.models import CustomUser


class RegistrationForm(UserCreationForm):
    """Creates a pending account whose email address must be verified."""

    email = forms.EmailField()

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ("email", "first_name", "last_name", "password1", "password2")

    def clean_email(self) -> str:
        email = self.cleaned_data["email"].lower()
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email address already exists.")
        return email


class LoginForm(forms.Form):
    """Email/password authentication with an explicit session-persistence choice."""

    email = forms.EmailField()
    password = forms.CharField(strip=False, widget=forms.PasswordInput)
    remember_me = forms.BooleanField(required=False)

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.user_cache = None

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")
        if email and password:
            self.user_cache = authenticate(self.request, email=email, password=password)
            if self.user_cache is None:
                raise ValidationError("Enter a valid email address and password.")
        return cleaned_data

    def get_user(self) -> CustomUser:
        return self.user_cache


class ResendVerificationForm(forms.Form):
    """Accepts an email without revealing whether an account exists."""

    email = forms.EmailField()


class MFACodeForm(forms.Form):
    """Accepts a six-digit authenticator code."""

    code = forms.RegexField(regex=r"^\d{6}$", max_length=6, min_length=6)


class MFADisableForm(forms.Form):
    """Requires a current password before a user removes MFA."""

    password = forms.CharField(strip=False, widget=forms.PasswordInput)

    def __init__(self, user: CustomUser, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_password(self) -> str:
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise ValidationError("Your password was not accepted.")
        return password
