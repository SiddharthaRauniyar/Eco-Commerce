"""Browser authentication views; APIs are deliberately deferred to Phase 15."""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import PasswordResetCompleteView, PasswordResetConfirmView, PasswordResetDoneView, PasswordResetView
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views import View
from django.views.generic import FormView, TemplateView

from apps.accounts.forms import (
    LoginForm,
    MFACodeForm,
    MFADisableForm,
    RegistrationForm,
    ResendVerificationForm,
)
from apps.accounts.mfa import decrypt_totp_secret, encrypt_totp_secret, generate_totp_secret, verify_totp
from apps.accounts.models import CustomUser, UserProfile
from apps.accounts.services import create_pending_user, login_is_locked, record_login_attempt, verify_user_email
from apps.accounts.tokens import email_verification_token


def _send_verification_email(request: HttpRequest, user: CustomUser) -> None:
    """Deliver a one-time activation link without exposing a reusable secret."""

    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    verification_url = request.build_absolute_uri(
        reverse("accounts:verify_email", kwargs={"uidb64": uidb64, "token": token})
    )
    body = render_to_string(
        "accounts/email_verification_email.txt", {"user": user, "verification_url": verification_url}
    )
    send_mail("Verify your Secure Commerce account", body, None, [user.email])


def _user_from_uid(uidb64: str) -> CustomUser | None:
    try:
        user_id = force_str(urlsafe_base64_decode(uidb64))
        return CustomUser.objects.filter(pk=user_id).first()
    except (TypeError, ValueError, OverflowError):
        return None


def _complete_login(request: HttpRequest, user: CustomUser, *, remember_me: bool) -> None:
    """Create the authenticated session only after all required factors pass."""

    login(request, user)
    request.session.set_expiry(60 * 60 * 24 * 14 if remember_me else 0)
    record_login_attempt(email=user.email, request=request, user=user, successful=True)


class RegistrationView(FormView):
    template_name = "accounts/register.html"
    form_class = RegistrationForm
    success_url = reverse_lazy("accounts:verification_sent")

    def form_valid(self, form):
        user = create_pending_user(form)
        _send_verification_email(self.request, user)
        return super().form_valid(form)


class VerificationSentView(TemplateView):
    template_name = "accounts/verification_sent.html"


class VerifyEmailView(View):
    """Activate a pending account when its signed token is valid."""

    def get(self, request: HttpRequest, uidb64: str, token: str) -> HttpResponse:
        user = _user_from_uid(uidb64)
        if user and email_verification_token.check_token(user, token):
            verify_user_email(user)
            messages.success(request, "Your email is verified. You can now sign in.")
            return redirect("accounts:login")
        messages.error(request, "That verification link is invalid or has expired.")
        return redirect("accounts:resend_verification")


class ResendVerificationView(FormView):
    template_name = "accounts/resend_verification.html"
    form_class = ResendVerificationForm
    success_url = reverse_lazy("accounts:verification_sent")

    def form_valid(self, form):
        user = CustomUser.objects.filter(email__iexact=form.cleaned_data["email"]).first()
        if user and not user.is_email_verified:
            _send_verification_email(self.request, user)
        return super().form_valid(form)


class AccountLoginView(FormView):
    template_name = "accounts/login.html"
    form_class = LoginForm
    success_url = reverse_lazy("accounts:profile")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def _lockout_response(self):
        form = self.get_form()
        form.add_error(None, "Too many sign-in attempts. Please try again later.")
        response = self.render_to_response(self.get_context_data(form=form), status=429)
        response["Retry-After"] = str(settings.LOGIN_LOCKOUT_SECONDS)
        return response

    def dispatch(self, request, *args, **kwargs):
        if request.method == "POST" and login_is_locked(request.POST.get("email", ""), request):
            return self._lockout_response()
        return super().dispatch(request, *args, **kwargs)

    def form_invalid(self, form):
        email = self.request.POST.get("email", "")
        user = CustomUser.objects.filter(email__iexact=email).first()
        if email:
            record_login_attempt(email=email, request=self.request, user=user, successful=False)
        if login_is_locked(email, self.request):
            return self._lockout_response()
        return super().form_invalid(form)

    def form_valid(self, form):
        user = form.get_user()
        profile, _ = UserProfile.objects.get_or_create(user=user)
        if profile.mfa_enabled:
            self.request.session.cycle_key()
            self.request.session["pending_mfa_user_id"] = user.pk
            self.request.session["pending_mfa_remember_me"] = form.cleaned_data["remember_me"]
            return redirect("accounts:mfa_challenge")
        _complete_login(self.request, user, remember_me=form.cleaned_data["remember_me"])
        return super().form_valid(form)


class MFAChallengeView(FormView):
    """Completes a pending password login with the user's authenticator code."""

    template_name = "accounts/mfa_challenge.html"
    form_class = MFACodeForm
    success_url = reverse_lazy("accounts:profile")

    def _pending_user(self) -> CustomUser:
        user_id = self.request.session.get("pending_mfa_user_id")
        user = CustomUser.objects.filter(pk=user_id, is_active=True).first()
        if user is None:
            raise Http404
        return user

    def dispatch(self, request, *args, **kwargs):
        user_id = request.session.get("pending_mfa_user_id")
        if not user_id:
            return redirect("accounts:login")
        user = CustomUser.objects.filter(pk=user_id, is_active=True).first()
        if user is None or login_is_locked(user.email, request):
            request.session.pop("pending_mfa_user_id", None)
            request.session.pop("pending_mfa_remember_me", None)
            messages.error(request, "Too many sign-in attempts. Please try again later.")
            return redirect("accounts:login")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = self._pending_user()
        try:
            profile, _ = UserProfile.objects.get_or_create(user=user)
            secret = decrypt_totp_secret(profile)
        except ValueError:
            self.request.session.pop("pending_mfa_user_id", None)
            self.request.session.pop("pending_mfa_remember_me", None)
            messages.error(self.request, "Multi-factor authentication needs to be set up again.")
            return redirect("accounts:login")

        if not verify_totp(secret, form.cleaned_data["code"]):
            record_login_attempt(
                email=user.email,
                request=self.request,
                user=user,
                successful=False,
                failure_reason="invalid_mfa_code",
            )
            if login_is_locked(user.email, self.request):
                self.request.session.pop("pending_mfa_user_id", None)
                self.request.session.pop("pending_mfa_remember_me", None)
                messages.error(self.request, "Too many sign-in attempts. Please try again later.")
                return redirect("accounts:login")
            form.add_error("code", "The authenticator code was not accepted.")
            return self.form_invalid(form)

        remember_me = bool(self.request.session.pop("pending_mfa_remember_me", False))
        self.request.session.pop("pending_mfa_user_id", None)
        _complete_login(self.request, user, remember_me=remember_me)
        return super().form_valid(form)


class MFASetupView(LoginRequiredMixin, FormView):
    """Enrol the current user by showing a one-time manual authenticator secret."""

    template_name = "accounts/mfa_setup.html"
    form_class = MFACodeForm
    success_url = reverse_lazy("accounts:profile")

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if profile.mfa_enabled:
            messages.info(request, "Multi-factor authentication is already enabled.")
            return redirect("accounts:profile")
        return super().dispatch(request, *args, **kwargs)

    def _profile_and_secret(self) -> tuple[UserProfile, str]:
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        if not profile.mfa_secret_encrypted:
            profile.mfa_secret_encrypted = encrypt_totp_secret(generate_totp_secret())
            profile.save(update_fields=("mfa_secret_encrypted", "updated_at"))
        return profile, decrypt_totp_secret(profile)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        _, secret = self._profile_and_secret()
        context["manual_secret"] = secret
        return context

    def form_valid(self, form):
        profile, secret = self._profile_and_secret()
        if not verify_totp(secret, form.cleaned_data["code"]):
            form.add_error("code", "The authenticator code was not accepted.")
            return self.form_invalid(form)
        profile.mfa_enabled = True
        profile.save(update_fields=("mfa_enabled", "updated_at"))
        messages.success(self.request, "Multi-factor authentication is now enabled.")
        return super().form_valid(form)


class MFADisableView(LoginRequiredMixin, FormView):
    """Disable MFA only after a current-password confirmation."""

    template_name = "accounts/mfa_disable.html"
    form_class = MFADisableForm
    success_url = reverse_lazy("accounts:profile")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    @transaction.atomic
    def form_valid(self, form):
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        profile.mfa_enabled = False
        profile.mfa_secret_encrypted = ""
        profile.save(update_fields=("mfa_enabled", "mfa_secret_encrypted", "updated_at"))
        messages.success(self.request, "Multi-factor authentication has been disabled.")
        return super().form_valid(form)


class ProfileView(LoginRequiredMixin, TemplateView):
    """Small authenticated landing page; profile editing arrives with customer UI."""

    template_name = "accounts/profile.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        UserProfile.objects.get_or_create(user=request.user)
        return super().dispatch(request, *args, **kwargs)


class AccountPasswordResetView(PasswordResetView):
    template_name = "accounts/password_reset_form.html"
    email_template_name = "accounts/password_reset_email.txt"
    subject_template_name = "accounts/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")


class AccountPasswordResetDoneView(PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class AccountPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")


class AccountPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"
