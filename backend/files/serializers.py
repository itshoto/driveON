from rest_framework import serializers

from . import health
from .models import TRASH_RETENTION, DriveFile


class DriveFileSerializer(serializers.ModelSerializer):
    # The account/google_file_id each chunk lives on is intentionally
    # never exposed -- the user shouldn't need to know where a file's
    # blocks physically live (SOP section 39). `health` summarizes chunk
    # availability instead of exposing per-chunk placement.
    health = serializers.SerializerMethodField()

    class Meta:
        model = DriveFile
        fields = [
            "id",
            "name",
            "mime_type",
            "size",
            "checksum",
            "status",
            "chunk_size",
            "replication_level",
            "category",
            "health",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_health(self, obj):
        # obj.chunks.all() reuses a prefetch_related("chunks", ...) cache
        # when the caller set one up, avoiding N+1 queries across a list.
        result = health.compute_health(obj, chunks=obj.chunks.all())
        return {
            "status": result.status,
            "chunks_available": result.chunks_available,
            "chunks_total": result.chunks_total,
            "redundancy_degraded": result.redundancy_degraded,
        }


class TrashedFileSerializer(DriveFileSerializer):
    purge_at = serializers.SerializerMethodField()

    class Meta(DriveFileSerializer.Meta):
        fields = DriveFileSerializer.Meta.fields + ["deleted_at", "purge_at"]
        read_only_fields = fields

    def get_purge_at(self, obj):
        return obj.deleted_at + TRASH_RETENTION if obj.deleted_at else None
