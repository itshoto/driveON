from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    max_google_accounts = serializers.SerializerMethodField()
    connected_google_accounts = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "created_at",
            "max_google_accounts",
            "connected_google_accounts",
        ]
        read_only_fields = fields

    def get_max_google_accounts(self, obj):
        return obj.max_google_accounts()

    def get_connected_google_accounts(self, obj):
        return obj.google_accounts.filter(status="connected").count()
