from datetime import timedelta

from django.conf import settings
from django.db import models

from accounts.models import StorageAccount

TRASH_RETENTION = timedelta(days=30)


def _default_chunk_size():
    return settings.CHUNK_SIZE_BYTES


class DriveFile(models.Model):
    """A file the user uploaded through driveON. Files are split into
    fixed-size chunks (see FileChunk) distributed across the user's
    connected storage accounts (Google Drive and/or OneDrive) by
    storage.allocator -- a file no longer lives on any single account."""

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

    REPLICATION_STANDARD = "standard"
    REPLICATION_SAFE = "safe"
    REPLICATION_MAXIMUM = "maximum"
    REPLICATION_CHOICES = [
        (REPLICATION_STANDARD, "Standard"),
        (REPLICATION_SAFE, "Safe"),
        (REPLICATION_MAXIMUM, "Maximum"),
    ]
    REPLICAS_BY_LEVEL = {
        REPLICATION_STANDARD: 1,
        REPLICATION_SAFE: 2,
        REPLICATION_MAXIMUM: 3,
    }

    CATEGORY_CHOICES = [
        ("research", "Research"),
        ("invoices", "Invoices"),
        ("legal", "Legal"),
        ("personal", "Personal"),
        ("datasets", "Datasets"),
        ("reports", "Reports"),
        ("other", "Other"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="files"
    )

    name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=255, blank=True)
    size = models.BigIntegerField(default=0)
    checksum = models.CharField(max_length=64, blank=True)

    # The block size actually used for this file's chunks, stamped at
    # upload time from settings.CHUNK_SIZE_BYTES -- kept per-file (not
    # re-read from settings at download time) so reconstruction stays
    # correct even if the global default changes later.
    chunk_size = models.BigIntegerField(default=_default_chunk_size)
    replication_level = models.CharField(
        max_length=20, choices=REPLICATION_CHOICES, default=REPLICATION_STANDARD
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_UPLOADING)

    # Non-null = in the recycle bin. Chunks aren't touched on the provider
    # side when this is set -- still counts against quota until purged,
    # same as a real Google Drive/OneDrive trash.
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # Set by ai.service.categorize_files (either automatically after
    # upload, or via an explicit user-triggered recategorize call). A
    # plain field here (not a table in the `ai` app) so it filters through
    # this file's existing Q-object machinery exactly like `type` does.
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, blank=True, db_index=True)
    categorized_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def replica_count(self):
        return self.REPLICAS_BY_LEVEL[self.replication_level]


class FileChunk(models.Model):
    """One physical copy of one fixed-size block of a DriveFile, stored on
    one connected storage account (Google Drive or OneDrive). A logical
    block at `index` may have several rows here (replica_number 0..N-1)
    when replication_level > 1; there's no separate "logical chunk" table
    since a block with zero physical copies doesn't exist -- every read
    path that matters (health, download, rebalancing) wants the physical
    rows directly."""

    STATUS_PENDING = "pending"
    STATUS_UPLOADING = "uploading"
    STATUS_AVAILABLE = "available"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_UPLOADING, "Uploading"),
        (STATUS_AVAILABLE, "Available"),
        (STATUS_FAILED, "Failed"),
    ]

    file = models.ForeignKey(DriveFile, on_delete=models.CASCADE, related_name="chunks")
    index = models.PositiveIntegerField()
    replica_number = models.PositiveIntegerField(default=0)

    account = models.ForeignKey(
        StorageAccount, on_delete=models.SET_NULL, null=True, related_name="chunks"
    )
    google_file_id = models.CharField(max_length=255, blank=True)

    size = models.BigIntegerField(default=0)
    checksum = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    bytes_transferred = models.BigIntegerField(default=0)

    upload_started_at = models.DateTimeField(null=True, blank=True)
    upload_completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["index", "replica_number"]
        constraints = [
            # Identity of one physical blob.
            models.UniqueConstraint(fields=["file", "index", "replica_number"], name="uniq_chunk_replica"),
            # No two replicas of the same logical block may share an
            # account -- that would defeat redundancy. Postgres treats
            # multiple NULL account rows as distinct, so a chunk that
            # failed and is awaiting reassignment doesn't collide with
            # another equally-unassigned one.
            models.UniqueConstraint(fields=["file", "index", "account"], name="uniq_chunk_account"),
        ]

    def __str__(self):
        return f"{self.file_id}#{self.index}.{self.replica_number}"
