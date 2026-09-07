"""Response headers that protect browser-rendered application pages."""

import secrets
from ipaddress import ip_address

from django.conf import settings


class TrustedProxyClientIPMiddleware:
    """Accept Nginx's overwritten client-IP header only at the configured boundary."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.TRUST_PROXY_HEADERS:
            try:
                request.META["REMOTE_ADDR"] = str(ip_address(request.META.get("HTTP_X_REAL_IP", "")))
            except ValueError:
                pass
        return self.get_response(request)


class SecurityHeadersMiddleware:
    """Add a per-response CSP nonce and conservative browser protections."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.csp_nonce = secrets.token_urlsafe(18)
        response = self.get_response(request)
        response.setdefault("Referrer-Policy", "same-origin")
        response.setdefault("Permissions-Policy", "camera=(), geolocation=(), microphone=(), payment=()")
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if response.get("Content-Type", "").startswith("text/html"):
            policy = [
                "default-src 'self'",
                "base-uri 'self'",
                "connect-src 'self'",
                "font-src 'self' data:",
                "form-action 'self'",
                "frame-ancestors 'none'",
                "frame-src 'none'",
                "img-src 'self' data:",
                "object-src 'none'",
                f"script-src 'self' https://cdn.jsdelivr.net 'nonce-{request.csp_nonce}'",
                "style-src 'self'",
            ]
            if settings.SECURE_SSL_REDIRECT:
                policy.append("upgrade-insecure-requests")
            response.setdefault("Content-Security-Policy", "; ".join(policy))
        return response
