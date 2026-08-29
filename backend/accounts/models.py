from django.conf import settings
from django.db import models


class StorageAccount(models.Model):
    """One connected third-party storage account (Google Drive or
    OneDrive) that driveON can place file chunks on."""

    PROVIDER_GOOGLE = "google"
    PROVIDER_MICROSOFT = "microsoft"
    PROVIDER_CHOICES = [
        (PROVIDER_GOOGLE, "Google Drive"),
        (PROVIDER_MICROSOFT, "OneDrive"),
    ]

    STATUS_CONNECTED = "connected"
    STATUS_DISCONNECTED = "disconnected"
    STATUS_ERROR = "error"
    STATUS_CHOICES = [
        (STATUS_CONNECTED, "Connected"),
        (STATUS_DISCONNECTED, "Disconnected"),
        (STATUS_ERROR, "Error"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="storage_accounts"
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    # Stable per-provider identity (Google's OpenID `sub` claim / Microsoft's
    # `oid` claim). Scoped uniqueness is per-provider, not global -- these
    # are two separate ID spaces that could theoretically collide as raw
    # strings. This is what prevents the same provider account being
    # connected to two driveON users -- see SOP section 8.
    provider_account_id = models.CharField(max_length=255)
    email = models.EmailField()
    display_name = models.CharField(max_length=255, blank=True)

    encrypted_access_token = models.TextField()
    encrypted_refresh_token = models.TextField()
    token_expiry = models.DateTimeField(null=True, blank=True)

    storage_total = models.BigIntegerField(default=0)
    storage_used = models.BigIntegerField(default=0)
    quota_checked_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_CONNECTED)

    # Inputs to storage.allocator's scoring function. avg_throughput_bps is
    # an exponential moving average updated after every chunk transfer
    # (upload or download); consecutive_errors increments on transfer
    # failure and resets to 0 on the next success, so it reflects "is this
    # account having trouble right now" rather than a lifetime tally.
    avg_throughput_bps = models.FloatField(null=True, blank=True)
    consecutive_errors = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["provider", "provider_account_id"], name="uniq_provider_account"),
        ]

    def __str__(self):
        return f"{self.email} ({self.user.username})"

    @property
    def storage_available(self):
        return max(self.storage_total - self.storage_used, 0)
