"""Focused coverage for browser headers, login lockouts, and upload validation."""

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.core.validators import validate_image_upload
from apps.security.models import ActivityLog, AuditLog, LoginAttempt, SecurityEvent
from apps.security.middleware import TrustedProxyClientIPMiddleware


class SecurityImplementationTests(TestCase):
    def test_trusted_proxy_replaces_the_peer_ip_only_when_enabled(self):
        request = RequestFactory().get(
            "/", REMOTE_ADDR="172.20.0.4", HTTP_X_REAL_IP="203.0.113.8"
        )
        middleware = TrustedProxyClientIPMiddleware(
            lambda current_request: HttpResponse(current_request.META["REMOTE_ADDR"])
        )

        self.assertEqual(middleware(request).content, b"172.20.0.4")
        with override_settings(TRUST_PROXY_HEADERS=True):
            self.assertEqual(middleware(request).content, b"203.0.113.8")

    def test_html_pages_receive_a_nonce_based_content_security_policy(self):
        response = self.client.get(reverse("core:home"))

        policy = response["Content-Security-Policy"]
        self.assertIn("default-src 'self'", policy)
        self.assertIn(f"'nonce-{response.wsgi_request.csp_nonce}'", policy)
        self.assertNotIn("unsafe-inline", policy)
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["X-Frame-Options"], "DENY")

    @override_settings(LOGIN_FAILURE_LIMIT=2, LOGIN_LOCKOUT_SECONDS=900)
    def test_repeated_failed_logins_lock_the_account_identifier_and_create_an_event(self):
        user = CustomUser.objects.create_user(
            "lockout@example.com", "Safe-authentication-pass-123", is_email_verified=True
        )

        self.client.post(reverse("accounts:login"), {"email": user.email, "password": "wrong-password"})
        locked_response = self.client.post(
            reverse("accounts:login"), {"email": user.email, "password": "wrong-password"}
        )
        valid_password_response = self.client.post(
            reverse("accounts:login"), {"email": user.email, "password": "Safe-authentication-pass-123"}
        )

        self.assertEqual(locked_response.status_code, 429)
        self.assertEqual(locked_response["Retry-After"], "900")
        self.assertEqual(valid_password_response.status_code, 429)
        self.assertEqual(LoginAttempt.objects.filter(email=user.email, successful=False).count(), 2)
        self.assertTrue(SecurityEvent.objects.filter(user=user, event_type="account.locked").exists())

    def test_upload_allow_list_rejects_an_executable_disguised_as_an_image(self):
        upload = SimpleUploadedFile("not-an-image.exe", b"not an image", content_type="image/jpeg")

        with self.assertRaises(ValidationError):
            validate_image_upload(upload)


class SecurityMonitoringTests(TestCase):
    def setUp(self):
        self.customer = CustomUser.objects.create_user("customer@example.com", "safe-test-password")
        self.analyst = CustomUser.objects.create_user("analyst@example.com", "safe-test-password", is_staff=True)
        self.observer = CustomUser.objects.create_user("observer@example.com", "safe-test-password", is_staff=True)
        permissions = Permission.objects.filter(content_type__app_label="security")
        self.analyst.user_permissions.set(permissions)
        self.observer.user_permissions.add(
            Permission.objects.get(content_type__app_label="security", codename="view_securityevent")
        )
        self.event = SecurityEvent.objects.create(
            user=self.customer,
            event_type="account.locked",
            severity=SecurityEvent.Severity.CRITICAL,
            description="Repeated failed sign-ins locked this account.",
            ip_address="127.0.0.1",
        )
        LoginAttempt.objects.create(
            user=self.customer,
            email=self.customer.email,
            ip_address="127.0.0.1",
            successful=False,
            failure_reason="invalid_credentials",
        )
        AuditLog.objects.create(
            actor=self.analyst,
            action="inventory.adjusted",
            target_type="products.Product",
            target_id="1",
        )
        ActivityLog.objects.create(actor=self.customer, action="account.signed_in")

    def test_security_analyst_sees_authorized_monitoring_data(self):
        self.client.force_login(self.analyst)

        response = self.client.get(reverse("security:monitoring"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Review signals, not customer secrets")
        self.assertContains(response, self.event.description)
        self.assertContains(response, self.customer.email)
        self.assertContains(response, "inventory.adjusted")
        self.assertContains(response, "Resolve")

    def test_event_observer_cannot_resolve_an_event(self):
        self.client.force_login(self.observer)

        response = self.client.post(reverse("security:resolve_event", kwargs={"event_id": self.event.pk}))

        self.assertEqual(response.status_code, 403)
        self.event.refresh_from_db()
        self.assertIsNone(self.event.resolved_at)

    def test_security_analyst_resolves_an_event_with_an_audit_record(self):
        self.client.force_login(self.analyst)

        response = self.client.post(reverse("security:resolve_event", kwargs={"event_id": self.event.pk}))

        self.assertRedirects(response, reverse("security:monitoring"))
        self.event.refresh_from_db()
        self.assertEqual(self.event.resolved_by, self.analyst)
        self.assertIsNotNone(self.event.resolved_at)
        self.assertTrue(
            AuditLog.objects.filter(action="security.event_resolved", target_id=str(self.event.pk)).exists()
        )
