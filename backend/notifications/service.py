from .models import Notification, NotificationPreference
from .tasks import send_notification_email

_PREFERENCE_FIELD_BY_CATEGORY = {
    Notification.CATEGORY_UPLOAD: "email_upload",
    Notification.CATEGORY_ACCOUNT: "email_account",
    Notification.CATEGORY_REBALANCE: "email_rebalance",
}


def _email_allowed(user, category):
    prefs, _ = NotificationPreference.objects.get_or_create(user=user)
    field = _PREFERENCE_FIELD_BY_CATEGORY.get(category)
    return getattr(prefs, field) if field else True


def notify(user, *, category, title, body="", level=Notification.LEVEL_INFO, link="", send_email=False):
    """Creates the Notification row synchronously -- cheap write, and it
    must be visible the instant the caller's operation completes (callers
    include poll loops like UploadProgress/RebalanceBanner that expect
    immediate consistency). Email is dispatched via a separate Celery task
    regardless of whether the caller is itself a request/response view or
    already running inside a Celery task -- inline send_mail would either
    add SMTP latency to a response, or hold a worker slot hostage to an
    SMTP round-trip for no benefit.

    `send_email=True` means "this category of event is email-worthy in
    general" -- the user's own per-category opt-out (Settings ->
    Notification Preferences) is enforced here, so trigger sites never
    need to know about preferences themselves.
    """
    notification = Notification.objects.create(
        user=user, category=category, level=level, title=title, body=body, link=link
    )
    if send_email and _email_allowed(user, category):
        send_notification_email.delay(notification.id)
    return notification
