from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core import signing
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from files import health, reconstruction
from files.models import DriveFile
from files.serializers import DriveFileSerializer
from users.models import User

from .models import FileCollaborator, ShareLink
from .serializers import FileCollaboratorSerializer, ShareLinkSerializer

# Short-lived: a password-unlocked download link only needs to survive the
# time between "Unlock" and the browser actually starting the download.
DOWNLOAD_TOKEN_SALT = "share-download"
DOWNLOAD_TOKEN_MAX_AGE_SECONDS = 600


def _owned_file_or_404(request, file_id):
    return get_object_or_404(DriveFile, id=file_id, user=request.user)


def _valid_link_or_none(token):
    """None for any reason a link shouldn't work anymore (missing, revoked,
    expired, or download-capped) -- callers don't need to distinguish why."""
    try:
        link = ShareLink.objects.select_related("file").get(token=token)
    except ShareLink.DoesNotExist:
        return None
    if link.revoked_at is not None:
        return None
    if link.expires_at is not None and link.expires_at <= timezone.now():
        return None
    if link.max_downloads is not None and link.download_count >= link.max_downloads:
        return None
    return link


class FileShareLinksView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, file_id):
        drive_file = _owned_file_or_404(request, file_id)
        links = drive_file.share_links.filter(revoked_at__isnull=True)
        return Response(ShareLinkSerializer(links, many=True).data)

    def post(self, request, file_id):
        drive_file = _owned_file_or_404(request, file_id)

        password = request.data.get("password") or ""
        expires_in_days = request.data.get("expires_in_days")
        max_downloads = request.data.get("max_downloads")

        link = ShareLink.objects.create(
            file=drive_file,
            created_by=request.user,
            password_hash=make_password(password) if password else "",
            expires_at=(timezone.now() + timedelta(days=int(expires_in_days))) if expires_in_days else None,
            max_downloads=int(max_downloads) if max_downloads else None,
        )
        data = ShareLinkSerializer(link).data
        data["url"] = f"{settings.FRONTEND_URL}/s/{link.token}"
        return Response(data, status=status.HTTP_201_CREATED)


class ShareLinkDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, link_id):
        link = get_object_or_404(ShareLink, id=link_id, created_by=request.user)
        link.revoked_at = timezone.now()
        link.save(update_fields=["revoked_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class PublicShareView(APIView):
    """The public landing page's metadata call -- no auth, since anonymous
    visitors are the whole point of a share link."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, token):
        link = _valid_link_or_none(token)
        if link is None:
            return Response({"detail": "This link is invalid or has expired."}, status=status.HTTP_404_NOT_FOUND)
        if link.password_hash:
            return Response({"requires_password": True, "name": link.file.name})
        return Response(
            {
                "requires_password": False,
                "name": link.file.name,
                "size": link.file.size,
                "mime_type": link.file.mime_type,
            }
        )


class PublicShareUnlockView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, token):
        link = _valid_link_or_none(token)
        if link is None:
            return Response({"detail": "This link is invalid or has expired."}, status=status.HTTP_404_NOT_FOUND)
        if not link.password_hash:
            return Response({"detail": "This link isn't password-protected."}, status=status.HTTP_400_BAD_REQUEST)

        password = request.data.get("password") or ""
        if not check_password(password, link.password_hash):
            return Response({"detail": "Incorrect password."}, status=status.HTTP_403_FORBIDDEN)

        dl_token = signing.dumps({"link_id": link.id}, salt=DOWNLOAD_TOKEN_SALT)
        return Response(
            {"dl": dl_token, "name": link.file.name, "size": link.file.size, "mime_type": link.file.mime_type}
        )


class PublicShareDownloadView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, token):
        link = _valid_link_or_none(token)
        if link is None:
            return Response({"detail": "This link is invalid or has expired."}, status=status.HTTP_404_NOT_FOUND)

        if link.password_hash:
            try:
                payload = signing.loads(
                    request.query_params.get("dl") or "",
                    salt=DOWNLOAD_TOKEN_SALT,
                    max_age=DOWNLOAD_TOKEN_MAX_AGE_SECONDS,
                )
            except signing.BadSignature:
                return Response({"detail": "Password verification required."}, status=status.HTTP_403_FORBIDDEN)
            if payload.get("link_id") != link.id:
                return Response({"detail": "Password verification required."}, status=status.HTTP_403_FORBIDDEN)

        drive_file = link.file
        if health.compute_health(drive_file).status == health.STATUS_UNAVAILABLE:
            return Response(
                {"detail": f"'{drive_file.name}' isn't reachable right now."},
                status=status.HTTP_409_CONFLICT,
            )

        link.download_count += 1
        link.save(update_fields=["download_count"])

        stream = reconstruction.stream_reconstructed(drive_file)
        safe_name = drive_file.name.replace('"', "").replace("\r", "").replace("\n", "")
        response = StreamingHttpResponse(stream, content_type=drive_file.mime_type or "application/octet-stream")
        response["Content-Disposition"] = f'attachment; filename="{safe_name}"'
        if drive_file.size:
            response["Content-Length"] = str(drive_file.size)
        return response


class SharedWithMeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        collaborations = (
            FileCollaborator.objects.filter(user=request.user, file__deleted_at__isnull=True)
            .select_related("file")
            .prefetch_related("file__chunks", "file__chunks__account")
        )
        files = [c.file for c in collaborations]
        return Response(DriveFileSerializer(files, many=True).data)


class FileCollaboratorsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, file_id):
        drive_file = _owned_file_or_404(request, file_id)
        collaborators = drive_file.collaborators.select_related("user")
        return Response(FileCollaboratorSerializer(collaborators, many=True).data)

    def post(self, request, file_id):
        drive_file = _owned_file_or_404(request, file_id)

        username = (request.data.get("username") or "").strip()
        role = request.data.get("role") or FileCollaborator.ROLE_VIEWER
        if role not in dict(FileCollaborator.ROLE_CHOICES):
            return Response({"detail": "role must be viewer or downloader."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            target_user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({"detail": "No driveON user with that username."}, status=status.HTTP_404_NOT_FOUND)
        if target_user.id == request.user.id:
            return Response({"detail": "You already own this file."}, status=status.HTTP_400_BAD_REQUEST)

        collaborator, _ = FileCollaborator.objects.update_or_create(
            file=drive_file, user=target_user, defaults={"role": role, "invited_by": request.user}
        )
        return Response(FileCollaboratorSerializer(collaborator).data, status=status.HTTP_201_CREATED)


class FileCollaboratorDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, file_id, user_id):
        drive_file = _owned_file_or_404(request, file_id)
        collaborator = get_object_or_404(FileCollaborator, file=drive_file, user_id=user_id)
        collaborator.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
