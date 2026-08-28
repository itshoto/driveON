import hashlib

from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from google_accounts.client import DriveService
from google_accounts.models import GoogleAccount
from storage.allocator import InsufficientStorageError, select_account_for_file

from .models import DriveFile
from .serializers import DriveFileSerializer

TYPE_PREFIXES = {
    "pdf": ["application/pdf"],
    "image": ["image/"],
    "video": ["video/"],
    "document": [
        "application/msword",
        "application/vnd.openxmlformats-officedocument",
        "text/",
    ],
    "archive": ["application/zip", "application/x-tar", "application/x-7z", "application/gzip"],
}


class FileListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = DriveFile.objects.filter(user=request.user)

        search = request.query_params.get("search")
        if search:
            qs = qs.filter(name__icontains=search)

        file_type = request.query_params.get("type")
        prefixes = TYPE_PREFIXES.get(file_type)
        if prefixes:
            from django.db.models import Q

            type_filter = Q()
            for prefix in prefixes:
                type_filter |= Q(mime_type__startswith=prefix)
            qs = qs.filter(type_filter)

        return Response(DriveFileSerializer(qs, many=True).data)


class FileUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        uploaded = request.FILES.get("file")
        if not uploaded:
            return Response({"detail": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

        max_bytes = request.user.plan.max_file_size_mb * 1024 * 1024 if request.user.plan else None
        if max_bytes and uploaded.size > max_bytes:
            return Response(
                {"detail": f"File exceeds your plan's {request.user.plan.max_file_size_mb} MB limit."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            account = select_account_for_file(request.user, uploaded.size)
        except InsufficientStorageError as exc:
            return Response(
                {
                    "detail": "Not enough combined storage.",
                    "required_bytes": exc.required,
                    "available_bytes": exc.available,
                    "short_by_bytes": max(exc.required - exc.available, 0),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        hasher = hashlib.sha256()
        for chunk in uploaded.chunks():
            hasher.update(chunk)
        checksum = hasher.hexdigest()
        uploaded.seek(0)

        drive_file = DriveFile.objects.create(
            user=request.user,
            google_account=account,
            name=uploaded.name,
            mime_type=uploaded.content_type or "application/octet-stream",
            size=uploaded.size,
            checksum=checksum,
            status=DriveFile.STATUS_UPLOADING,
        )

        try:
            result = DriveService(account).upload_file_streaming(
                uploaded, uploaded.name, drive_file.mime_type
            )
        except Exception:
            drive_file.status = DriveFile.STATUS_FAILED
            drive_file.save(update_fields=["status", "updated_at"])
            return Response(
                {"detail": "Upload to Google Drive failed. Please retry."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        drive_file.google_file_id = result["id"]
        drive_file.status = DriveFile.STATUS_AVAILABLE
        drive_file.save(update_fields=["google_file_id", "status", "updated_at"])

        account.storage_used += uploaded.size
        account.save(update_fields=["storage_used", "updated_at"])

        return Response(DriveFileSerializer(drive_file).data, status=status.HTTP_201_CREATED)


class FileDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, file_id):
        drive_file = get_object_or_404(DriveFile, id=file_id, user=request.user)
        return Response(DriveFileSerializer(drive_file).data)

    def patch(self, request, file_id):
        drive_file = get_object_or_404(DriveFile, id=file_id, user=request.user)
        new_name = (request.data.get("name") or "").strip()
        if not new_name:
            return Response({"detail": "name is required."}, status=status.HTTP_400_BAD_REQUEST)

        if drive_file.google_account is None or drive_file.google_account.status != GoogleAccount.STATUS_CONNECTED:
            return Response(
                {"detail": "This file's Google account is disconnected and cannot be modified."},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            DriveService(drive_file.google_account).rename_file(drive_file.google_file_id, new_name)
        except Exception:
            return Response({"detail": "Rename failed. Please retry."}, status=status.HTTP_502_BAD_GATEWAY)

        drive_file.name = new_name
        drive_file.save(update_fields=["name", "updated_at"])
        return Response(DriveFileSerializer(drive_file).data)

    def delete(self, request, file_id):
        drive_file = get_object_or_404(DriveFile, id=file_id, user=request.user)

        if drive_file.google_account is not None and drive_file.google_account.status == GoogleAccount.STATUS_CONNECTED:
            try:
                DriveService(drive_file.google_account).delete_file(drive_file.google_file_id)
                drive_file.google_account.storage_used = max(
                    drive_file.google_account.storage_used - drive_file.size, 0
                )
                drive_file.google_account.save(update_fields=["storage_used", "updated_at"])
            except Exception:
                pass  # If it's already gone on Drive's side, deleting our record is still correct.

        drive_file.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FileDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, file_id):
        drive_file = get_object_or_404(DriveFile, id=file_id, user=request.user)

        if drive_file.status == DriveFile.STATUS_PARTIALLY_AVAILABLE or drive_file.google_account is None:
            return Response(
                {
                    "detail": (
                        f"'{drive_file.name}' cannot currently be downloaded because the "
                        "connected Google Drive account holding it is unavailable."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        if drive_file.google_account.status != GoogleAccount.STATUS_CONNECTED:
            return Response(
                {"detail": f"'{drive_file.name}' is unavailable: its Google account is disconnected."},
                status=status.HTTP_409_CONFLICT,
            )

        stream = DriveService(drive_file.google_account).download_file_stream(drive_file.google_file_id)
        safe_name = drive_file.name.replace('"', "").replace("\r", "").replace("\n", "")
        response = StreamingHttpResponse(
            stream, content_type=drive_file.mime_type or "application/octet-stream"
        )
        response["Content-Disposition"] = f'attachment; filename="{safe_name}"'
        if drive_file.size:
            response["Content-Length"] = str(drive_file.size)
        return response
