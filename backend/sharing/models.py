import secrets

from django.conf import settings
from django.db import models


def _generate_token():
    return secrets.token_urlsafe(24)


class ShareLink(models.Model):
    """A public, token-addressed link to one file. Optionally
    password-protected, expiring, and/or capped at a download count."""

    file = models.ForeignKey("files.DriveFile", on_delete=models.CASCADE, related_name="share_links")
    token = models.CharField(max_length=64, unique=True, default=_generate_token)
    password_hash = models.CharField(max_length=255, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    max_downloads = models.PositiveIntegerField(null=True, blank=True)
    download_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="share_links")
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"share:{self.token} -> {self.file_id}"


class FileCollaborator(models.Model):
    """Grants another driveON user read access to one of the caller's
    files. Deliberately no "editor" tier in v1 -- letting a collaborator
    rename/delete someone else's file is a materially bigger trust
    boundary than read access, and nothing needs it yet."""

    ROLE_VIEWER = "viewer"
    ROLE_DOWNLOADER = "downloader"
    ROLE_CHOICES = [(ROLE_VIEWER, "Viewer"), (ROLE_DOWNLOADER, "Downloader")]

    file = models.ForeignKey("files.DriveFile", on_delete=models.CASCADE, related_name="collaborators")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shared_files")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_VIEWER)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["file", "user"], name="uniq_file_collaborator")]

    def __str__(self):
        return f"{self.user_id} -> {self.file_id} ({self.role})"
