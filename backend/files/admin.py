from django.contrib import admin

from .models import DriveFile, FileChunk


@admin.register(DriveFile)
class DriveFileAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "status", "size", "category", "replication_level", "deleted_at", "created_at"]
    list_filter = ["status", "category", "replication_level"]
    search_fields = ["name", "user__username", "checksum"]


@admin.register(FileChunk)
class FileChunkAdmin(admin.ModelAdmin):
    """Read-only-in-spirit -- useful for debugging distributed placement,
    not meant to be hand-edited (mutating a chunk row here wouldn't touch
    the actual provider-side blob)."""

    list_display = ["file", "index", "replica_number", "account", "status", "size"]
    list_filter = ["status"]
    search_fields = ["file__name"]
