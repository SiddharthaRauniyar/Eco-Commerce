"""Short-lived, user-bound tokens for email-address verification."""

from django.contrib.auth.tokens import PasswordResetTokenGenerator


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """Invalidates a token immediately after the account has been verified."""

    def _make_hash_value(self, user, timestamp: int) -> str:
        return f"{user.pk}{user.password}{user.is_email_verified}{timestamp}"


email_verification_token = EmailVerificationTokenGenerator()
