import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

from .models import Notification

logger = logging.getLogger(__name__)


@shared_task
def send_notification_email(notification_id):
    """Best-effort -- failure here must never surface to whatever
    triggered the notification (same posture as e.g.
    accounts.client.revoke_refresh_token)."""
    try:
        notification = Notification.objects.select_related("user").get(id=notification_id)
    except Notification.DoesNotExist:
        return

    message = notification.body
    if notification.link:
        message = f"{message}\n\n{settings.FRONTEND_URL}{notification.link}"

    try:
        send_mail(
            subject=f"driveON: {notification.title}",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[notification.user.email],
            fail_silently=False,
        )
        notification.email_sent = True
        notification.save(update_fields=["email_sent"])
    except Exception:
        logger.exception("Failed to send notification email id=%s", notification_id)
