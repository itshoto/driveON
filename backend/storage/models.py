from django.conf import settings
from django.db import models


class RebalanceRun(models.Model):
    """One execution of storage.tasks.rebalance_user -- tracked so the
    frontend can poll progress after POST /api/storage/rebalance/trigger."""

    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_RUNNING, "Running"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="rebalance_runs")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RUNNING)
    chunks_planned = models.PositiveIntegerField(default=0)
    chunks_moved = models.PositiveIntegerField(default=0)
    errors_count = models.PositiveIntegerField(default=0)

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]
