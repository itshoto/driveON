from rest_framework import serializers

from .models import FileCollaborator, ShareLink


class ShareLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShareLink
        # password_hash is intentionally never serialized out.
        fields = ["id", "token", "expires_at", "max_downloads", "download_count", "revoked_at", "created_at"]
        read_only_fields = fields


class FileCollaboratorSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = FileCollaborator
        # user_id (not just the FileCollaborator row's own id) is required
        # by the frontend, since DELETE .../collaborators/<user_id> is
        # keyed on the user, not this join row.
        fields = ["id", "user_id", "username", "email", "role", "created_at"]
        read_only_fields = fields
