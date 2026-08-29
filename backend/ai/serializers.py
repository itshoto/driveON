from rest_framework import serializers

from .models import AIConversation, AIMessage


class AIMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIMessage
        fields = ["id", "role", "content", "created_at"]
        read_only_fields = fields


class AIConversationSerializer(serializers.ModelSerializer):
    file_ids = serializers.SerializerMethodField()

    class Meta:
        model = AIConversation
        fields = ["id", "title", "file_ids", "created_at", "updated_at"]
        read_only_fields = fields

    def get_file_ids(self, obj):
        return list(obj.conversation_files.values_list("drive_file_id", flat=True))


class AIConversationDetailSerializer(AIConversationSerializer):
    messages = AIMessageSerializer(many=True, read_only=True)

    class Meta(AIConversationSerializer.Meta):
        fields = AIConversationSerializer.Meta.fields + ["messages"]
        read_only_fields = fields
