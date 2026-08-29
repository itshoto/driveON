from rest_framework import serializers

from .models import StorageAccount


class StorageAccountSerializer(serializers.ModelSerializer):
    storage_available = serializers.SerializerMethodField()

    class Meta:
        model = StorageAccount
        fields = [
            "id",
            "provider",
            "email",
            "display_name",
            "storage_total",
            "storage_used",
            "storage_available",
            "status",
            "quota_checked_at",
            "created_at",
        ]
        read_only_fields = fields

    def get_storage_available(self, obj):
        return obj.storage_available
