"""TOTP helpers using the RFC 6238 algorithm and encrypted secret storage."""

import base64
import binascii
import hashlib
import hmac
import re
import secrets
import time

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

from apps.accounts.models import UserProfile

_OTP_PATTERN = re.compile(r"^\d{6}$")


def _fernet() -> Fernet:
    """Return the configured deployment key or a safe local-development key."""

    configured_key = settings.MFA_ENCRYPTION_KEY
    if configured_key:
        return Fernet(configured_key.encode("ascii"))

    derived_key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
    return Fernet(derived_key)


def generate_totp_secret() -> str:
    """Create a 160-bit Base32 authenticator secret without padding."""

    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def encrypt_totp_secret(secret: str) -> str:
    """Encrypt the secret before it is placed in the profile row."""

    return _fernet().encrypt(secret.encode("ascii")).decode("ascii")


def decrypt_totp_secret(profile: UserProfile) -> str:
    """Recover a previously enrolled TOTP secret for server-side validation."""

    if not profile.mfa_secret_encrypted:
        raise ValueError("No MFA secret is enrolled for this profile.")
    try:
        return _fernet().decrypt(profile.mfa_secret_encrypted.encode("ascii")).decode("ascii")
    except InvalidToken as exc:
        raise ValueError("The MFA secret cannot be decrypted with the active key.") from exc


def _totp_at(secret: str, counter: int) -> str:
    padding = "=" * (-len(secret) % 8)
    try:
        key = base64.b32decode(f"{secret.upper()}{padding}", casefold=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("The stored MFA secret is invalid.") from exc
    digest = hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary_code = int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF
    return f"{binary_code % 1_000_000:06d}"


def verify_totp(secret: str, code: str, *, now: float | None = None, valid_window: int = 1) -> bool:
    """Accept the current six-digit code plus one 30-second clock-skew window."""

    candidate = code.strip()
    if not _OTP_PATTERN.fullmatch(candidate):
        return False
    counter = int((time.time() if now is None else now) // 30)
    return any(
        hmac.compare_digest(_totp_at(secret, counter + offset), candidate)
        for offset in range(-valid_window, valid_window + 1)
    )
