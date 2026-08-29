from django.conf import settings
from django.db import models


class Notification(models.Model):
    CATEGORY_UPLOAD = "upload"
    CATEGORY_ACCOUNT = "account"
    CATEGORY_REBALANCE = "rebalance"
    CATEGORY_CHOICES = [
        (CATEGORY_UPLOAD, "Upload"),
        (CATEGORY_ACCOUNT, "Account"),
        (CATEGORY_REBALANCE, "Rebalance"),
    ]

    LEVEL_INFO = "info"
    LEVEL_WARNING = "warning"
    LEVEL_CRITICAL = "critical"
    LEVEL_CHOICES = [
        (LEVEL_INFO, "Info"),
        (LEVEL_WARNING, "Warning"),
        (LEVEL_CRITICAL, "Critical"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default=LEVEL_INFO)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    # A frontend *section* path ("/files", "/drives"), never a deep object
    # link -- the underlying DriveFile/RebalanceRun this refers to may not
    # exist or be relevant anymore by the time this is read, and there's
    # no FK here to keep it honest.
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    email_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "is_read"])]

    def __str__(self):
        return f"{self.title} ({self.user_id})"


class NotificationPreference(models.Model):
    """Per-user opt-out of email for a notification category. A missing
    row (get_or_create in the service layer) means "email everything" --
    the default posture matches what trigger sites already ask for."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_preference"
    )
    email_upload = models.BooleanField(default=True)
    email_account = models.BooleanField(default=True)
    email_rebalance = models.BooleanField(default=True)
