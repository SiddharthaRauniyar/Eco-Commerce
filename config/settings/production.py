"""Fail-closed settings for the containerized production deployment."""

import os

from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403


def _required(name: str) -> str:
    """Return a required environment value without silently accepting blanks."""
    value = os.environ.get(name, "")
    if not value.strip():
        raise ImproperlyConfigured(f"{name} is required in production.")
    return value


def _env_bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).lower() in {"1", "true", "yes", "on"}


def _looks_like_placeholder(value: str) -> bool:
    return not value.strip() or value.strip().lower().startswith(
        ("django-insecure-", "unsafe-", "change", "replace", "your-")
    )


DEBUG = False

_secret = SECRET_KEY.strip()  # noqa: F405
if _looks_like_placeholder(_secret):
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be a real production secret.")

ALLOWED_HOSTS = [  # noqa: F405
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
    if host.strip()
]
_placeholder_hosts = {"example.com", "www.example.com", "localhost", "127.0.0.1", "::1"}
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS or any(
    host.lstrip(".").lower() in _placeholder_hosts
    or host.lstrip(".").lower().endswith((".example.com", ".example.invalid", ".example.test"))
    for host in ALLOWED_HOSTS
):
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must contain real production host names.")

_postgres_port = os.environ.get("POSTGRES_PORT", "5432")
try:
    int(_postgres_port)
except ValueError as exc:
    raise ImproperlyConfigured("POSTGRES_PORT must be an integer.") from exc

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _required("POSTGRES_DB"),
        "USER": _required("POSTGRES_USER"),
        "PASSWORD": _required("POSTGRES_PASSWORD"),
        "HOST": _required("POSTGRES_HOST"),
        "PORT": _postgres_port,
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
    }
}

REDIS_URL = _required("REDIS_URL")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "TIMEOUT": 300,
        "KEY_PREFIX": os.environ.get("DJANGO_CACHE_KEY_PREFIX", "secure-commerce"),
    }
}

_disabled_email_backends = {
    "django.core.mail.backends.console.EmailBackend",
    "django.core.mail.backends.dummy.EmailBackend",
    "django.core.mail.backends.locmem.EmailBackend",
}
if EMAIL_BACKEND in _disabled_email_backends or not EMAIL_HOST:  # noqa: F405
    raise ImproperlyConfigured("Configure a non-console email backend and DJANGO_EMAIL_HOST in production.")
if ".example." in EMAIL_HOST.lower() or ".example." in DEFAULT_FROM_EMAIL.lower():  # noqa: F405
    raise ImproperlyConfigured("Configure real email host and sender values in production.")

_jwt_signing_key = os.environ.get("JWT_SIGNING_KEY", "")
if _jwt_signing_key and _looks_like_placeholder(_jwt_signing_key):
    raise ImproperlyConfigured("JWT_SIGNING_KEY must be real when it is set.")

_mfa_key = os.environ.get("MFA_ENCRYPTION_KEY", "")
if _mfa_key:
    try:
        Fernet(_mfa_key.encode("ascii"))
    except (UnicodeEncodeError, ValueError) as exc:
        raise ImproperlyConfigured("MFA_ENCRYPTION_KEY must be a valid Fernet key.") from exc

STORAGES = {
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
    }
}

TRUST_PROXY_HEADERS = _env_bool("DJANGO_TRUST_PROXY_HEADERS", False)
if not TRUST_PROXY_HEADERS:
    raise ImproperlyConfigured("DJANGO_TRUST_PROXY_HEADERS=true is required behind the production proxy.")

SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool("DJANGO_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = _env_bool("DJANGO_HSTS_PRELOAD", False)
