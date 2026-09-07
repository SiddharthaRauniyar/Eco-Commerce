"""Configuration checks that protect local development usability."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.test import TestCase, override_settings
from django.urls import reverse
from django.views.static import serve


class AdminAndMediaConfigurationTests(TestCase):
    @override_settings(DEBUG=True)
    def test_media_configuration_builds_a_development_file_server_pattern(self):
        pattern = static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)[0]
        match = pattern.resolve(f"{settings.MEDIA_URL.lstrip('/')}product-images/2026/08/milk.jpeg")

        self.assertIs(match.func, serve)
        self.assertEqual(match.kwargs["document_root"], settings.MEDIA_ROOT)

    def test_admin_has_secure_commerce_branding_and_dashboard(self):
        self.assertEqual(admin.site.site_header, "Secure Commerce Operations")
        user = self._create_superuser()
        login_response = self.client.post(
            reverse("admin:login"),
            {
                "username": user.email,
                "password": "safe-test-password",
                "next": reverse("admin:index"),
            },
        )

        self.assertRedirects(login_response, reverse("admin:index"))

        response = self.client.get(reverse("admin:index"))

        self.assertContains(response, "Run the store with clarity.")
        self.assertContains(response, "css/admin.css")

    def test_admin_logout_keeps_the_storefront_session_active(self):
        user = self._create_superuser()
        self.client.post(
            reverse("admin:login"),
            {
                "username": user.email,
                "password": "safe-test-password",
                "next": reverse("admin:index"),
            },
        )

        response = self.client.post(reverse("admin:logout"))

        self.assertRedirects(response, reverse("admin:login"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 200)
        self.assertRedirects(
            self.client.get(reverse("admin:index")),
            f"{reverse('admin:login')}?next={reverse('admin:index')}",
        )

    def test_staff_storefront_session_cannot_bypass_admin_login(self):
        self.client.force_login(self._create_superuser())

        self.assertRedirects(
            self.client.get(reverse("admin:index")),
            f"{reverse('admin:login')}?next={reverse('admin:index')}",
        )

    def _create_superuser(self):
        from apps.accounts.models import CustomUser

        return CustomUser.objects.create_superuser("admin@example.com", "safe-test-password")
