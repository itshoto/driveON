from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from files.models import DriveFile

from . import service, tasks
from .client import is_configured
from .models import AIConversation, AIConversationFile, AISummary
from .quota import AIQuotaExceededError, assert_quota_available, current_usage
from .serializers import AIConversationDetailSerializer, AIConversationSerializer

MAX_CHAT_FILES = 5


def _unconfigured_response():
    return Response({"detail": "AI features aren't configured."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


def _quota_error_response(exc):
    return Response(
        {
            "detail": f"You've used {exc.used}/{exc.limit} AI queries this month.",
            "used": exc.used,
            "limit": exc.limit,
        },
        status=status.HTTP_429_TOO_MANY_REQUESTS,
    )


class AIQuotaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        used, limit = current_usage(request.user)
        return Response({"used": used, "limit": limit})


class FileSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, file_id):
        drive_file = get_object_or_404(DriveFile, id=file_id, user=request.user)
        try:
            summary = drive_file.ai_summary
        except AISummary.DoesNotExist:
            return Response({"detail": "No summary requested for this file yet."}, status=status.HTTP_404_NOT_FOUND)
        return Response(
            {
                "file_id": drive_file.id,
                "status": "ready",
                "model": summary.model,
                "generated_at": summary.created_at,
                "summary": summary.summary,
            }
        )

    def post(self, request, file_id):
        if not is_configured():
            return _unconfigured_response()

        drive_file = get_object_or_404(DriveFile, id=file_id, user=request.user)

        # Already generated -- return the cached result, no new API call.
        try:
            existing = drive_file.ai_summary
            return Response(
                {
                    "file_id": drive_file.id,
                    "status": "ready",
                    "model": existing.model,
                    "generated_at": existing.created_at,
                    "summary": existing.summary,
                }
            )
        except AISummary.DoesNotExist:
            pass

        try:
            service.check_document_eligible(drive_file)
        except service.AIDocumentError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

        try:
            assert_quota_available(request.user)
        except AIQuotaExceededError as exc:
            return _quota_error_response(exc)

        tasks.generate_summary_task.delay(drive_file.id)
        return Response({"file_id": drive_file.id, "status": "processing"}, status=status.HTTP_202_ACCEPTED)


class ConversationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        conversations = AIConversation.objects.filter(user=request.user)
        return Response(AIConversationSerializer(conversations, many=True).data)

    def post(self, request):
        if not is_configured():
            return _unconfigured_response()

        file_ids = request.data.get("file_ids") or []
        if not file_ids:
            return Response({"detail": "file_ids is required."}, status=status.HTTP_400_BAD_REQUEST)
        if len(file_ids) > MAX_CHAT_FILES:
            return Response(
                {"detail": f"You can attach at most {MAX_CHAT_FILES} files."}, status=status.HTTP_400_BAD_REQUEST
            )

        files = list(DriveFile.objects.filter(id__in=file_ids, user=request.user))
        if len(files) != len(set(file_ids)):
            return Response({"detail": "One or more files weren't found."}, status=status.HTTP_404_NOT_FOUND)

        for drive_file in files:
            try:
                service.check_document_eligible(drive_file)
            except service.AIDocumentError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

        # Reconstruction/upload to Claude is deferred to the first message
        # (see service.send_chat_message) -- this call only writes rows.
        conversation = AIConversation.objects.create(
            user=request.user, title=", ".join(f.name for f in files)[:255]
        )
        AIConversationFile.objects.bulk_create(
            [AIConversationFile(conversation=conversation, drive_file=f) for f in files]
        )
        return Response(AIConversationSerializer(conversation).data, status=status.HTTP_201_CREATED)


class ConversationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        conversation = get_object_or_404(AIConversation, id=conversation_id, user=request.user)
        return Response(AIConversationDetailSerializer(conversation).data)

    def delete(self, request, conversation_id):
        conversation = get_object_or_404(AIConversation, id=conversation_id, user=request.user)
        service.delete_conversation(conversation)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ConversationMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, conversation_id):
        if not is_configured():
            return _unconfigured_response()

        conversation = get_object_or_404(AIConversation, id=conversation_id, user=request.user)
        content = (request.data.get("content") or "").strip()
        if not content:
            return Response({"detail": "content is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            assert_quota_available(request.user)
        except AIQuotaExceededError as exc:
            return _quota_error_response(exc)

        try:
            reply = service.send_chat_message(conversation, content)
        except service.AIDocumentError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        used, limit = current_usage(request.user)
        return Response({"message": {"role": "assistant", "content": reply}, "quota": {"used": used, "limit": limit}})


class SearchView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not is_configured():
            return _unconfigured_response()

        query = (request.data.get("query") or "").strip()
        if not query:
            return Response({"detail": "query is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            assert_quota_available(request.user)
        except AIQuotaExceededError as exc:
            return _quota_error_response(exc)

        return Response(service.search_files(request.user, query))


class CategorizeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not is_configured():
            return _unconfigured_response()

        file_ids = request.data.get("file_ids")
        if file_ids:
            qs = DriveFile.objects.filter(id__in=file_ids, user=request.user, deleted_at__isnull=True)
        else:
            qs = DriveFile.objects.filter(user=request.user, deleted_at__isnull=True, category="")
        ids = list(qs.values_list("id", flat=True))
        if not ids:
            return Response({"status": "done", "batches": 0, "detail": "No files to categorize."})

        try:
            assert_quota_available(request.user)
        except AIQuotaExceededError as exc:
            return _quota_error_response(exc)

        batch_size = settings.AI_CATEGORIZE_BATCH_SIZE
        batches = [ids[i : i + batch_size] for i in range(0, len(ids), batch_size)]
        for batch in batches:
            tasks.categorize_files_task.delay(batch, billable=True)

        return Response({"status": "processing", "batches": len(batches)}, status=status.HTTP_202_ACCEPTED)
