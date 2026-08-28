from django.urls import path

from .views import MeView, SyncView

urlpatterns = [
    path("sync", SyncView.as_view(), name="auth-sync"),
    path("me", MeView.as_view(), name="auth-me"),
]
