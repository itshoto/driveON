from django.contrib import admin

from .models import AIConversation, AISummary, AIUsageLog


@admin.register(AIUsageLog)
class AIUsageLogAdmin(admin.ModelAdmin):
    list_display = ["user", "feature", "billable", "input_tokens", "output_tokens", "created_at"]
    list_filter = ["feature", "billable"]
    search_fields = ["user__username"]


@admin.register(AISummary)
class AISummaryAdmin(admin.ModelAdmin):
    list_display = ["drive_file", "model", "created_at"]
    search_fields = ["drive_file__name"]


@admin.register(AIConversation)
class AIConversationAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "created_at", "updated_at"]
    search_fields = ["title", "user__username"]
