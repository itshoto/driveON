from django.contrib import admin

from .models import FileCollaborator, ShareLink


@admin.register(ShareLink)
class ShareLinkAdmin(admin.ModelAdmin):
    list_display = ["token", "file", "created_by", "download_count", "max_downloads", "expires_at", "revoked_at"]
    search_fields = ["token", "file__name", "created_by__username"]


@admin.register(FileCollaborator)
class FileCollaboratorAdmin(admin.ModelAdmin):
    list_display = ["file", "user", "role", "invited_by", "created_at"]
    list_filter = ["role"]
    search_fields = ["file__name", "user__username"]
