from django.urls import path

from .views import (
    NotificationListView,
    NotificationMarkAllReadView,
    NotificationMarkReadView,
    NotificationPreferenceView,
    NotificationUnreadCountView,
)

urlpatterns = [
    path("", NotificationListView.as_view(), name="notification-list"),
    path("unread-count", NotificationUnreadCountView.as_view(), name="notification-unread-count"),
    path("<int:notification_id>/read", NotificationMarkReadView.as_view(), name="notification-mark-read"),
    path("read-all", NotificationMarkAllReadView.as_view(), name="notification-mark-all-read"),
    path("preferences", NotificationPreferenceView.as_view(), name="notification-preferences"),
]
