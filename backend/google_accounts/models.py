from django.conf import settings
from django.db import models


class GoogleAccount(models.Model):
    STATUS_CONNECTED = "connected"
    STATUS_DISCONNECTED = "disconnected"
    STATUS_ERROR = "error"
    STATUS_CHOICES = [
        (STATUS_CONNECTED, "Connected"),
        (STATUS_DISCONNECTED, "Disconnected"),
        (STATUS_ERROR, "Error"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="google_accounts"
    )
    # Stable Google account identifier (OpenID Connect `sub` claim). This is
    # what prevents the same Google account being connected to two driveON
    # users -- see SOP section 8.
    google_account_id = models.CharField(max_length=255, unique=True)
    email = models.EmailField()
    display_name = models.CharField(max_length=255, blank=True)

    encrypted_access_token = models.TextField()
    encrypted_refresh_token = models.TextField()
    token_expiry = models.DateTimeField(null=True, blank=True)

    storage_total = models.BigIntegerField(default=0)
    storage_used = models.BigIntegerField(default=0)
    quota_checked_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_CONNECTED)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.email} ({self.user.username})"

    @property
    def storage_available(self):
        return max(self.storage_total - self.storage_used, 0)
