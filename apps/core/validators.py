"""Small allow-list validators for browser-uploaded files."""

from pathlib import Path

from django.core.exceptions import ValidationError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
IMAGE_SUFFIXES = {".gif", ".jpeg", ".jpg", ".png", ".webp"}
SUPPORT_SUFFIXES = IMAGE_SUFFIXES | {".pdf", ".txt"}


def _validate_upload(upload, allowed_suffixes: set[str]) -> None:
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError("Uploads must be 5 MB or smaller.")
    if Path(upload.name).suffix.lower() not in allowed_suffixes:
        raise ValidationError("This file type is not allowed.")


def validate_image_upload(upload) -> None:
    _validate_upload(upload, IMAGE_SUFFIXES)


def validate_support_upload(upload) -> None:
    _validate_upload(upload, SUPPORT_SUFFIXES)
