from django.urls import path

from .views import (
    FileDetailView,
    FileDownloadView,
    FileDuplicatesView,
    FileListView,
    FilePreviewView,
    FilePurgeView,
    FileRestoreView,
    FileStatsView,
    FileUploadStatusView,
    FileUploadView,
    TrashListView,
)

urlpatterns = [
    path("", FileListView.as_view(), name="file-list"),
    path("upload", FileUploadView.as_view(), name="file-upload"),
    path("stats", FileStatsView.as_view(), name="file-stats"),
    path("duplicates", FileDuplicatesView.as_view(), name="file-duplicates"),
    path("trash", TrashListView.as_view(), name="file-trash"),
    path("<int:file_id>", FileDetailView.as_view(), name="file-detail"),
    path("<int:file_id>/download", FileDownloadView.as_view(), name="file-download"),
    path("<int:file_id>/preview", FilePreviewView.as_view(), name="file-preview"),
    path("<int:file_id>/upload-status", FileUploadStatusView.as_view(), name="file-upload-status"),
    path("<int:file_id>/restore", FileRestoreView.as_view(), name="file-restore"),
    path("<int:file_id>/purge", FilePurgeView.as_view(), name="file-purge"),
]
