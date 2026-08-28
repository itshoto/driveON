from django.urls import path

from .views import StorageSummaryView

urlpatterns = [
    path("summary", StorageSummaryView.as_view(), name="storage-summary"),
]
