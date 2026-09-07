"""Identity, profile, and customer address models."""

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models

from apps.core.models import TimeStampedModel
from apps.core.validators import validate_image_upload


class CustomUserManager(BaseUserManager):
    """Creates users with email as the canonical login identifier."""

    use_in_migrations = True

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if extra_fields.get("is_staff") is not True or extra_fields.get("is_superuser") is not True:
            raise ValueError("A superuser must have is_staff=True and is_superuser=True.")
        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractUser, TimeStampedModel):
    """Project user model; created before the first migration by design."""

    username = None
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    is_email_verified = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []
    objects = CustomUserManager()

    def __str__(self) -> str:
        return self.email


class UserProfile(TimeStampedModel):
    """Optional customer preferences and security metadata kept off the user row."""

    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="profile")
    phone_number = models.CharField(max_length=32, blank=True)
    avatar = models.FileField(upload_to="profile-avatars/%Y/%m/", blank=True, validators=[validate_image_upload])
    date_of_birth = models.DateField(null=True, blank=True)
    newsletter_opt_in = models.BooleanField(default=False)
    marketing_opt_in = models.BooleanField(default=False)
    mfa_enabled = models.BooleanField(default=False)
    mfa_secret_encrypted = models.CharField(max_length=255, blank=True)

    def __str__(self) -> str:
        return f"Profile for {self.user.email}"


class Address(TimeStampedModel):
    """Reusable customer shipping and billing address."""

    phone_validator = RegexValidator(r"^[0-9+() -]{7,32}$", "Enter a valid phone number.")

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField(max_length=80, default="Home")
    recipient_name = models.CharField(max_length=255)
    line1 = models.CharField(max_length=255)
    line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=128)
    region = models.CharField(max_length=128, blank=True)
    postal_code = models.CharField(max_length=32)
    country_code = models.CharField(max_length=2)
    phone_number = models.CharField(max_length=32, validators=[phone_validator], blank=True)
    is_default_shipping = models.BooleanField(default=False)
    is_default_billing = models.BooleanField(default=False)

    class Meta:
        ordering = ("-is_default_shipping", "-updated_at")

    def __str__(self) -> str:
        return f"{self.label}: {self.recipient_name}"
