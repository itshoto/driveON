from django.http import Http404

from .models import DriveFile


def get_accessible_file(request, file_id, require_download=False):
    """Returns the DriveFile if `request.user` owns it, or has collaborator
    access to it (role must be `downloader` when require_download=True,
    any role otherwise). 404s rather than 403 either way, so a file's
    existence/collaborator list is never revealed to a non-collaborator.

    Only used by the three read paths (detail/download/preview) --
    rename/delete/restore/purge stay strictly owner-only, since v1 sharing
    grants read access only (see sharing.models.FileCollaborator)."""
    try:
        return DriveFile.objects.get(id=file_id, user=request.user)
    except DriveFile.DoesNotExist:
        pass

    # Local import: files must not depend on sharing at module level (same
    # convention as files' existing local imports of accounts/notifications).
    from sharing.models import FileCollaborator

    collab_qs = FileCollaborator.objects.filter(
        file_id=file_id, user=request.user, file__deleted_at__isnull=True
    )
    if require_download:
        collab_qs = collab_qs.filter(role=FileCollaborator.ROLE_DOWNLOADER)
    collaborator = collab_qs.select_related("file").first()
    if collaborator is None:
        raise Http404
    return collaborator.file
