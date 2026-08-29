from django.contrib import admin

from .models import Notification, NotificationPreference


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "category", "level", "is_read", "email_sent", "created_at"]
    list_filter = ["category", "level", "is_read", "email_sent"]
    search_fields = ["title", "user__username"]


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ["user", "email_upload", "email_account", "email_rebalance"]
