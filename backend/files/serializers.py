from rest_framework import serializers

from .models import DriveFile


class DriveFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriveFile
        # google_account / google_file_id are intentionally omitted -- the
        # user shouldn't need to know where a file physically lives
        # (SOP section 39).
        fields = ["id", "name", "mime_type", "size", "checksum", "status", "created_at", "updated_at"]
        read_only_fields = fields
