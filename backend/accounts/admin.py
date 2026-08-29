from django.contrib import admin

from .models import StorageAccount


@admin.register(StorageAccount)
class StorageAccountAdmin(admin.ModelAdmin):
    list_display = ["email", "provider", "user", "status", "storage_used", "storage_total", "created_at"]
    list_filter = ["provider", "status"]
    search_fields = ["email", "user__username"]
