from django.urls import path

from .views import FileDetailView, FileDownloadView, FileListView, FileUploadView

urlpatterns = [
    path("", FileListView.as_view(), name="file-list"),
    path("upload", FileUploadView.as_view(), name="file-upload"),
    path("<int:file_id>", FileDetailView.as_view(), name="file-detail"),
    path("<int:file_id>/download", FileDownloadView.as_view(), name="file-download"),
]
