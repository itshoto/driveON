from django.conf import settings
from django.db import models

from google_accounts.models import GoogleAccount


class DriveFile(models.Model):
    """A file the user uploaded through driveON. Phase 2 scope: each file
    lives whole on a single connected Google account (no chunking yet --
    see storage.allocator and SOP phase split, section 58)."""

    STATUS_UPLOADING = "uploading"
    STATUS_AVAILABLE = "available"
    STATUS_PARTIALLY_AVAILABLE = "partially_available"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_UPLOADING, "Uploading"),
        (STATUS_AVAILABLE, "Available"),
        (STATUS_PARTIALLY_AVAILABLE, "Partially available"),
        (STATUS_FAILED, "Failed"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="files"
    )
    google_account = models.ForeignKey(
        GoogleAccount, on_delete=models.SET_NULL, null=True, related_name="files"
    )
    google_file_id = models.CharField(max_length=255, blank=True)

    name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=255, blank=True)
    size = models.BigIntegerField(default=0)
    checksum = models.CharField(max_length=64, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_UPLOADING)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name
