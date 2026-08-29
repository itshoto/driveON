from django.urls import path

from .views import (
    FileCollaboratorDetailView,
    FileCollaboratorsView,
    FileShareLinksView,
    PublicShareDownloadView,
    PublicShareUnlockView,
    PublicShareView,
    ShareLinkDetailView,
    SharedWithMeView,
)

urlpatterns = [
    path("files/<int:file_id>/links", FileShareLinksView.as_view(), name="share-links"),
    path("links/<int:link_id>", ShareLinkDetailView.as_view(), name="share-link-detail"),
    path("public/<str:token>", PublicShareView.as_view(), name="share-public"),
    path("public/<str:token>/unlock", PublicShareUnlockView.as_view(), name="share-public-unlock"),
    path("public/<str:token>/download", PublicShareDownloadView.as_view(), name="share-public-download"),
    path("shared-with-me", SharedWithMeView.as_view(), name="shared-with-me"),
    path("files/<int:file_id>/collaborators", FileCollaboratorsView.as_view(), name="file-collaborators"),
    path(
        "files/<int:file_id>/collaborators/<int:user_id>",
        FileCollaboratorDetailView.as_view(),
        name="file-collaborator-detail",
    ),
]
