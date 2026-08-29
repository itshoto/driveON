from django.contrib import admin

from .models import Plan, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ["username", "email", "plan", "is_active", "is_staff", "created_at"]
    list_filter = ["is_active", "is_staff", "plan"]
    search_fields = ["username", "email", "firebase_uid"]


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ["name", "max_connected_accounts", "max_file_size_mb", "ai_queries_per_month"]
