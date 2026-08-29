from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import StorageAccount
from accounts.serializers import StorageAccountSerializer

from . import allocator, tasks
from .models import RebalanceRun


class StorageSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        accounts = StorageAccount.objects.filter(
            user=request.user, status=StorageAccount.STATUS_CONNECTED
        )
        total = sum(a.storage_total for a in accounts)
        used = sum(a.storage_used for a in accounts)
        return Response(
            {
                "total": total,
                "used": used,
                "available": max(total - used, 0),
                "accounts": StorageAccountSerializer(accounts, many=True).data,
            }
        )


class RebalanceCheckView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(allocator.check_imbalance(request.user))


class RebalanceTriggerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        run = RebalanceRun.objects.create(user=request.user)
        tasks.rebalance_user.delay(run.id)
        return Response({"run_id": run.id}, status=status.HTTP_202_ACCEPTED)


class RebalanceStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, run_id):
        run = get_object_or_404(RebalanceRun, id=run_id, user=request.user)
        return Response(
            {
                "status": run.status,
                "chunks_planned": run.chunks_planned,
                "chunks_moved": run.chunks_moved,
                "errors_count": run.errors_count,
            }
        )
