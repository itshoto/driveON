import os
import re
from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.db.models import Count, Q, Sum
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.client import get_client
from accounts.models import StorageAccount
from storage import allocator

from . import health, reconstruction, tasks
from .models import TRASH_RETENTION, DriveFile
from .permissions import get_accessible_file
from .serializers import DriveFileSerializer, TrashedFileSerializer

TYPE_PREFIXES = {
    "pdf": ["application/pdf"],
    "image": ["image/"],
    "video": ["video/"],
    "audio": ["audio/"],
    "document": [
        "application/msword",
        "application/vnd.openxmlformats-officedocument",
        "text/",
    ],
    "archive": ["application/zip", "application/x-tar", "application/x-7z", "application/gzip"],
}

# Whitelisted, since sorting directly on user input would let arbitrary
# model fields be probed/leaked through ordering side-channels.
ORDERING_FIELDS = {
    "name": "name",
    "-name": "-name",
    "size": "size",
    "-size": "-size",
    "type": "mime_type",
    "-type": "-mime_type",
    "modified": "updated_at",
    "-modified": "-updated_at",
    "created": "created_at",
    "-created": "-created_at",
}
DEFAULT_ORDERING = "-created_at"

# Raster formats only -- SVG is XML and can carry a <script>, so it's
# deliberately excluded from inline preview (SOP: never render
# user-supplied markup in driveON's own origin).
PREVIEWABLE_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/bmp",
    "image/x-icon",
}
PREVIEWABLE_PDF_TYPE = "application/pdf"


def _type_filter(prefixes):
    q = Q()
    for prefix in prefixes:
        q |= Q(mime_type__startswith=prefix)
    return q


def _known_type_filter():
    q = Q()
    for prefixes in TYPE_PREFIXES.values():
        q |= _type_filter(prefixes)
    return q


def _filter_for_type(file_type):
    """Q object for the `type` query param, or None if it's absent/unknown.
    "other" is anything that doesn't fall into one of TYPE_PREFIXES'
    categories, so it has to be derived rather than looked up directly."""
    if file_type == "other":
        return ~_known_type_filter()
    prefixes = TYPE_PREFIXES.get(file_type)
    return _type_filter(prefixes) if prefixes else None


def _prefetch_chunks(qs):
    return qs.prefetch_related("chunks", "chunks__account")


SIZE_UNITS = {"b": 1, "kb": 1024, "mb": 1024**2, "gb": 1024**3, "tb": 1024**4}


def _parse_size(value):
    match = re.match(r"^([\d.]+)\s*(b|kb|mb|gb|tb)?$", value.strip(), re.IGNORECASE)
    if not match:
        return None
    number, unit = match.groups()
    try:
        number = float(number)
    except ValueError:
        return None
    return int(number * SIZE_UNITS[(unit or "b").lower()])


def _parse_size_filter(value):
    """`size:>500MB`, `size:<1GB`, `size:100MB..1GB`. Returns None (never
    raises) on anything unrecognized so the token falls back to plain
    free-text search instead of erroring the whole query."""
    value = value.strip()
    if ".." in value:
        low_raw, high_raw = value.split("..", 1)
        low, high = _parse_size(low_raw), _parse_size(high_raw)
        if low is None and high is None:
            return None
        q = Q()
        if low is not None:
            q &= Q(size__gte=low)
        if high is not None:
            q &= Q(size__lte=high)
        return q
    for op, lookup in ((">=", "gte"), ("<=", "lte"), (">", "gt"), ("<", "lt")):
        if value.startswith(op):
            size_bytes = _parse_size(value[len(op):])
            return Q(**{f"size__{lookup}": size_bytes}) if size_bytes is not None else None
    size_bytes = _parse_size(value)
    return Q(size=size_bytes) if size_bytes is not None else None


def _parse_modified_filter(value):
    """`modified:today`, `modified:thisweek`, `modified:last30days`."""
    value = value.strip().lower()
    now = timezone.now()
    if value == "today":
        return Q(updated_at__gte=now.replace(hour=0, minute=0, second=0, microsecond=0))
    if value == "thisweek":
        start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        return Q(updated_at__gte=start)
    match = re.match(r"^last(\d+)days?$", value)
    if match:
        return Q(updated_at__gte=now - timedelta(days=int(match.group(1))))
    return None


ADVANCED_FILTER_PARSERS = {"size": _parse_size_filter, "modified": _parse_modified_filter}


def _parse_advanced_query(raw):
    """Splits `raw` into (free_text, type_value, [Q, ...]) by pulling
    recognized key:value tokens (type:, size:, modified:) out of a search
    string -- everything else, including an unrecognized key:value token,
    stays in the free-text name search rather than erroring the query."""
    free_text_parts = []
    extra_filters = []
    type_value = None
    for token in raw.split():
        key, sep, value = token.partition(":")
        if sep and value:
            key = key.lower()
            if key == "type":
                type_value = value
                continue
            parser = ADVANCED_FILTER_PARSERS.get(key)
            if parser:
                parsed = parser(value)
                if parsed is not None:
                    extra_filters.append(parsed)
                    continue
        free_text_parts.append(token)
    return " ".join(free_text_parts), type_value, extra_filters


def _purge_file(drive_file, chunks=None):
    """Permanently removes a file: best-effort deletes every chunk's blob
    from its provider, decrements that account's storage_used, then
    deletes the DriveFile row (cascades its FileChunk rows). Shared by
    FilePurgeView (one file, on request) and the recycle bin's lazy
    expiry sweep (many files, prefetched)."""
    rows = chunks if chunks is not None else drive_file.chunks.select_related("account")
    for chunk in rows:
        account = chunk.account
        if account is None or account.status != StorageAccount.STATUS_CONNECTED or not chunk.google_file_id:
            continue
        try:
            get_client(account).delete_file(chunk.google_file_id)
            account.storage_used = max(account.storage_used - chunk.size, 0)
            account.save(update_fields=["storage_used", "updated_at"])
        except Exception:
            pass  # If it's already gone on the provider's side, deleting our record is still correct.
    drive_file.delete()


def _purge_expired_trash(user):
    """Trash has no scheduled sweep (no Celery Beat in this app, same
    posture as rebalancing) -- instead, anything past the retention
    window gets purged the next time the user actually opens their trash.
    Effectively "30 days, purged next time you look", not "purged by a
    clock"."""
    cutoff = timezone.now() - TRASH_RETENTION
    expired = DriveFile.objects.filter(
        user=user, deleted_at__isnull=False, deleted_at__lte=cutoff
    ).prefetch_related("chunks", "chunks__account")
    for drive_file in expired:
        _purge_file(drive_file, chunks=drive_file.chunks.all())


class FileListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = DriveFile.objects.filter(user=request.user, deleted_at__isnull=True)

        type_param = request.query_params.get("type")
        search = request.query_params.get("search")
        if search:
            # Advanced syntax lives entirely in the free-text search box --
            # e.g. "type:pdf size:>500MB modified:last30days report" -- so
            # no frontend change is needed to support it.
            free_text, advanced_type, extra_filters = _parse_advanced_query(search)
            if free_text:
                qs = qs.filter(name__icontains=free_text)
            for extra_filter in extra_filters:
                qs = qs.filter(extra_filter)
            if advanced_type and not type_param:
                type_param = advanced_type

        type_filter = _filter_for_type(type_param)
        if type_filter is not None:
            qs = qs.filter(type_filter)

        category = request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)

        ordering = ORDERING_FIELDS.get(request.query_params.get("ordering"), DEFAULT_ORDERING)
        qs = _prefetch_chunks(qs.order_by(ordering))

        return Response(DriveFileSerializer(qs, many=True).data)


class FileDuplicatesView(APIView):
    """Groups the caller's files by whole-file checksum (already computed
    by files.tasks.process_upload) to surface exact duplicates and how much
    space reclaiming them would free up."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = DriveFile.objects.filter(user=request.user, deleted_at__isnull=True).exclude(checksum="")
        duplicate_checksums = (
            qs.values("checksum").annotate(n=Count("id")).filter(n__gt=1).values_list("checksum", flat=True)
        )

        groups = []
        total_reclaimable = 0
        for checksum in duplicate_checksums:
            files = list(qs.filter(checksum=checksum).order_by("created_at"))
            reclaimable = sum(f.size for f in files[1:])  # every copy after the oldest
            total_reclaimable += reclaimable
            groups.append({"files": DriveFileSerializer(files, many=True).data, "reclaimable_bytes": reclaimable})

        return Response({"groups": groups, "total_reclaimable_bytes": total_reclaimable})


class FileStatsView(APIView):
    """Counts of the caller's files per type category, for the file browser's
    "N images / N videos / ..." summary. Independent of any active
    search/type filter on the list view. Trashed files don't count."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = DriveFile.objects.filter(user=request.user, deleted_at__isnull=True)

        counts = {key: qs.filter(_type_filter(prefixes)).count() for key, prefixes in TYPE_PREFIXES.items()}
        counts["other"] = qs.filter(_filter_for_type("other")).count()
        counts["total"] = qs.count()

        # Kept as a separate key rather than reshaping `counts` itself, so
        # existing callers reading counts[type] as a bare number (the Files
        # page's stat chips) don't need to change.
        sizes = {
            key: qs.filter(_type_filter(prefixes)).aggregate(total=Sum("size"))["total"] or 0
            for key, prefixes in TYPE_PREFIXES.items()
        }
        sizes["other"] = qs.filter(_filter_for_type("other")).aggregate(total=Sum("size"))["total"] or 0
        sizes["total"] = qs.aggregate(total=Sum("size"))["total"] or 0
        counts["sizes"] = sizes

        return Response(counts)


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

        replication = request.data.get("replication") or DriveFile.REPLICATION_STANDARD
        if replication not in DriveFile.REPLICAS_BY_LEVEL:
            return Response(
                {"detail": "replication must be one of: standard, safe, maximum."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        copies = DriveFile.REPLICAS_BY_LEVEL[replication]

        connected_count = StorageAccount.objects.filter(
            user=request.user, status=StorageAccount.STATUS_CONNECTED
        ).count()
        if copies > connected_count:
            return Response(
                {"detail": f"This redundancy level needs at least {copies} connected account(s); you have {connected_count}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            allocator.check_capacity(request.user, uploaded.size * copies)
        except allocator.InsufficientStorageError as exc:
            return Response(
                {
                    "detail": "Not enough combined storage.",
                    "required_bytes": exc.required,
                    "available_bytes": exc.available,
                    "short_by_bytes": max(exc.required - exc.available, 0),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        os.makedirs(settings.CHUNK_UPLOAD_TMP_DIR, exist_ok=True)
        temp_path = os.path.join(settings.CHUNK_UPLOAD_TMP_DIR, f"{uuid4().hex}.upload")
        with open(temp_path, "wb") as dst:
            for block in uploaded.chunks():
                dst.write(block)

        mime_type = uploaded.content_type or "application/octet-stream"
        drive_file = DriveFile.objects.create(
            user=request.user,
            name=uploaded.name,
            mime_type=mime_type,
            size=uploaded.size,
            status=DriveFile.STATUS_UPLOADING,
            chunk_size=settings.CHUNK_SIZE_BYTES,
            replication_level=replication,
        )

        tasks.process_upload.delay(drive_file.id, temp_path, mime_type)

        return Response(DriveFileSerializer(drive_file).data, status=status.HTTP_202_ACCEPTED)


class FileUploadStatusView(APIView):
    """Polled by the frontend while a file's status is "uploading" to
    render per-account progress bars and a combined transfer rate."""

    permission_classes = [IsAuthenticated]

    def get(self, request, file_id):
        drive_file = get_object_or_404(DriveFile, id=file_id, user=request.user)
        chunks = list(drive_file.chunks.select_related("account"))

        bytes_total = 0
        bytes_transferred = 0
        indices_total = set()
        indices_available = set()
        by_account = {}

        for chunk in chunks:
            indices_total.add(chunk.index)
            bytes_total += chunk.size
            bytes_transferred += chunk.bytes_transferred
            if chunk.status == chunk.STATUS_AVAILABLE:
                indices_available.add(chunk.index)

            if chunk.account is not None:
                entry = by_account.setdefault(
                    chunk.account_id,
                    {
                        "account_id": chunk.account_id,
                        "email": chunk.account.email,
                        "provider": chunk.account.provider,
                        "bytes_transferred": 0,
                        "bytes_total": 0,
                    },
                )
                entry["bytes_total"] += chunk.size
                entry["bytes_transferred"] += chunk.bytes_transferred

        return Response(
            {
                "status": drive_file.status,
                "bytes_total": bytes_total,
                "bytes_transferred": bytes_transferred,
                "chunks_available": len(indices_available),
                "chunks_total": len(indices_total),
                "accounts": list(by_account.values()),
            }
        )


class FileDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, file_id):
        drive_file = get_accessible_file(request, file_id)
        return Response(DriveFileSerializer(drive_file).data)

    def patch(self, request, file_id):
        drive_file = get_object_or_404(DriveFile, id=file_id, user=request.user)
        new_name = (request.data.get("name") or "").strip()
        if not new_name:
            return Response({"detail": "name is required."}, status=status.HTTP_400_BAD_REQUEST)

        # A file's blocks live under internal names (name.part3.r0) on
        # the provider that the user never sees, so renaming is DB-only --
        # no provider API call, no failure mode here.
        drive_file.name = new_name
        drive_file.save(update_fields=["name", "updated_at"])
        return Response(DriveFileSerializer(drive_file).data)

    def delete(self, request, file_id):
        """Moves the file to the recycle bin. Nothing on the provider side
        is touched yet -- see TrashListView/FileRestoreView/FilePurgeView."""
        drive_file = get_object_or_404(DriveFile, id=file_id, user=request.user, deleted_at__isnull=True)
        drive_file.deleted_at = timezone.now()
        drive_file.save(update_fields=["deleted_at", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class TrashListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        _purge_expired_trash(request.user)
        qs = DriveFile.objects.filter(user=request.user, deleted_at__isnull=False).order_by("-deleted_at")
        return Response(TrashedFileSerializer(_prefetch_chunks(qs), many=True).data)


class FileRestoreView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, file_id):
        drive_file = get_object_or_404(DriveFile, id=file_id, user=request.user, deleted_at__isnull=False)
        drive_file.deleted_at = None
        drive_file.save(update_fields=["deleted_at", "updated_at"])
        return Response(DriveFileSerializer(drive_file).data)


class FilePurgeView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, file_id):
        drive_file = get_object_or_404(DriveFile, id=file_id, user=request.user, deleted_at__isnull=False)
        _purge_file(drive_file)
        return Response(status=status.HTTP_204_NO_CONTENT)


class FileDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, file_id):
        drive_file = get_accessible_file(request, file_id, require_download=True)

        if health.compute_health(drive_file).status == health.STATUS_UNAVAILABLE:
            return Response(
                {
                    "detail": (
                        f"'{drive_file.name}' cannot currently be downloaded because some of its "
                        "data isn't reachable right now."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        stream = reconstruction.stream_reconstructed(drive_file)
        safe_name = drive_file.name.replace('"', "").replace("\r", "").replace("\n", "")
        response = StreamingHttpResponse(
            stream, content_type=drive_file.mime_type or "application/octet-stream"
        )
        response["Content-Disposition"] = f'attachment; filename="{safe_name}"'
        if drive_file.size:
            response["Content-Length"] = str(drive_file.size)
        return response


class FilePreviewView(APIView):
    """Streams a file's content inline (no download prompt) for in-app
    viewing. Restricted to raster images and PDFs -- the only types the
    frontend renders directly -- and to files that are currently fully
    reconstructable (see files.health)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, file_id):
        drive_file = get_accessible_file(request, file_id)

        previewable = (
            drive_file.mime_type in PREVIEWABLE_IMAGE_TYPES
            or drive_file.mime_type == PREVIEWABLE_PDF_TYPE
        )
        if not previewable:
            return Response(
                {"detail": "This file type can't be previewed in-app. Download it instead."},
                status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            )

        if health.compute_health(drive_file).status == health.STATUS_UNAVAILABLE:
            return Response(
                {"detail": f"'{drive_file.name}' isn't fully available and can't be previewed."},
                status=status.HTTP_409_CONFLICT,
            )

        stream = reconstruction.stream_reconstructed(drive_file)
        safe_name = drive_file.name.replace('"', "").replace("\r", "").replace("\n", "")
        response = StreamingHttpResponse(stream, content_type=drive_file.mime_type)
        response["Content-Disposition"] = f'inline; filename="{safe_name}"'
        response["X-Content-Type-Options"] = "nosniff"
        if drive_file.size:
            response["Content-Length"] = str(drive_file.size)
        return response
