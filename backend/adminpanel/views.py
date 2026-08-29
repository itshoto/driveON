import redis
from celery import current_app
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView

from accounts.models import StorageAccount
from files.models import DriveFile
from storage.models import RebalanceRun
from users.models import User


def _ping_celery():
    """Number of workers that responded -- 0 means background jobs
    (uploads, rebalancing, AI summaries/categorization) won't process."""
    try:
        replies = current_app.control.ping(timeout=1)
        return len(replies)
    except Exception:
        return 0


def _ping_redis():
    try:
        return bool(redis.from_url(settings.CELERY_BROKER_URL).ping())
    except Exception:
        return False


@method_decorator(staff_member_required, name="dispatch")
class DashboardView(TemplateView):
    """Cross-app stats/health snapshot -- deliberately not inside any one
    feature app. Reuses Django's own admin session auth (is_staff), not
    Firebase; see users.models.UserManager.create_superuser for how to
    get an account that can actually log in here."""

    template_name = "adminpanel/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "user_count": User.objects.count(),
                "accounts_by_provider": StorageAccount.objects.values("provider").annotate(n=Count("id")),
                "file_count": DriveFile.objects.filter(deleted_at__isnull=True).count(),
                "distributed_file_count": DriveFile.objects.annotate(
                    n_accounts=Count("chunks__account", distinct=True)
                )
                .filter(n_accounts__gt=1)
                .count(),
                "active_uploads": DriveFile.objects.filter(status=DriveFile.STATUS_UPLOADING).count(),
                "failed_uploads": DriveFile.objects.filter(status=DriveFile.STATUS_FAILED).count(),
                "failed_rebalances": RebalanceRun.objects.filter(status=RebalanceRun.STATUS_FAILED).count(),
                "celery_workers": _ping_celery(),
                "redis_ok": _ping_redis(),
            }
        )
        return context
