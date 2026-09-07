"""End-to-end checks for the Phase 3 browser authentication controls."""

import time

from django.contrib.auth.models import Group
from django.core import mail
from django.test import TestCase, override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.urls import reverse

from apps.accounts.mfa import _totp_at, encrypt_totp_secret, generate_totp_secret
from apps.accounts.models import CustomUser, UserProfile
from apps.accounts.rbac import sync_role_groups
from apps.accounts.tokens import email_verification_token


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AuthenticationFlowTests(TestCase):
    def test_registration_verification_activates_account_and_creates_profile(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "email": "new@example.com",
                "first_name": "New",
                "last_name": "Customer",
                "password1": "Safe-authentication-pass-123",
                "password2": "Safe-authentication-pass-123",
            },
        )

        self.assertRedirects(response, reverse("accounts:verification_sent"))
        user = CustomUser.objects.get(email="new@example.com")
        self.assertFalse(user.is_active)
        self.assertFalse(user.is_email_verified)
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        self.assertEqual(len(mail.outbox), 1)

        confirmation = self.client.get(
            reverse(
                "accounts:verify_email",
                kwargs={
                    "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
                    "token": email_verification_token.make_token(user),
                },
            )
        )
        self.assertRedirects(confirmation, reverse("accounts:login"))
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_email_verified)

    def test_mfa_login_requires_a_valid_totp_code_before_session_login(self):
        user = CustomUser.objects.create_user(
            email="mfa@example.com", password="Safe-authentication-pass-123", is_email_verified=True
        )
        secret = generate_totp_secret()
        UserProfile.objects.create(
            user=user, mfa_enabled=True, mfa_secret_encrypted=encrypt_totp_secret(secret)
        )

        password_response = self.client.post(
            reverse("accounts:login"), {"email": user.email, "password": "Safe-authentication-pass-123"}
        )
        self.assertRedirects(password_response, reverse("accounts:mfa_challenge"))
        self.assertNotIn("_auth_user_id", self.client.session)

        code = _totp_at(secret, int(time.time() // 30))
        mfa_response = self.client.post(reverse("accounts:mfa_challenge"), {"code": code})
        self.assertRedirects(mfa_response, reverse("accounts:profile"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_role_sync_creates_least_privilege_groups(self):
        counts = sync_role_groups()

        self.assertIn("Security Analyst", counts)
        security_group = Group.objects.get(name="Security Analyst")
        self.assertTrue(security_group.permissions.filter(codename="view_securityevent").exists())
        self.assertFalse(security_group.permissions.filter(codename="change_product").exists())

    def test_password_reset_sends_a_one_time_link_for_active_accounts(self):
        CustomUser.objects.create_user(
            email="reset@example.com", password="Safe-authentication-pass-123", is_email_verified=True
        )

        response = self.client.post(reverse("accounts:password_reset"), {"email": "reset@example.com"})

        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("password-reset/", mail.outbox[0].body)

    def test_login_page_uses_the_shared_accessible_design_system(self):
        response = self.client.get(reverse("accounts:login"))

        self.assertContains(response, "css/app.css")
        self.assertContains(response, "data-theme-toggle")
        self.assertContains(response, "Skip to content")
