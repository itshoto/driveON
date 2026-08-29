from django.utils import timezone

from .models import AIUsageLog


class AIQuotaExceededError(Exception):
    def __init__(self, used, limit):
        self.used = used
        self.limit = limit
        super().__init__(f"Used {used}/{limit} AI queries this month")


def _month_start():
    return timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def current_usage(user):
    limit = user.plan.ai_queries_per_month if user.plan else 0
    used = AIUsageLog.objects.filter(user=user, billable=True, created_at__gte=_month_start()).count()
    return used, limit


def assert_quota_available(user):
    used, limit = current_usage(user)
    if used >= limit:
        raise AIQuotaExceededError(used, limit)


def record_usage(user, feature, *, drive_file=None, conversation=None, input_tokens=0, output_tokens=0, billable=True):
    return AIUsageLog.objects.create(
        user=user,
        feature=feature,
        drive_file=drive_file,
        conversation=conversation,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        billable=billable,
    )
