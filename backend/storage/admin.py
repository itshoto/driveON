from django.contrib import admin

from .models import RebalanceRun


@admin.register(RebalanceRun)
class RebalanceRunAdmin(admin.ModelAdmin):
    list_display = ["user", "status", "chunks_planned", "chunks_moved", "errors_count", "started_at", "finished_at"]
    list_filter = ["status"]
