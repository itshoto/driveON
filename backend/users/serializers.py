from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    max_connected_accounts = serializers.SerializerMethodField()
    connected_accounts = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "created_at",
            "max_connected_accounts",
            "connected_accounts",
        ]
        read_only_fields = fields

    def get_max_connected_accounts(self, obj):
        return obj.max_connected_accounts()

    def get_connected_accounts(self, obj):
        return obj.storage_accounts.filter(status="connected").count()
