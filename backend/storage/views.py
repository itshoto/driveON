from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from google_accounts.models import GoogleAccount
from google_accounts.serializers import GoogleAccountSerializer


class StorageSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        accounts = GoogleAccount.objects.filter(
            user=request.user, status=GoogleAccount.STATUS_CONNECTED
        )
        total = sum(a.storage_total for a in accounts)
        used = sum(a.storage_used for a in accounts)
        return Response(
            {
                "total": total,
                "used": used,
                "available": max(total - used, 0),
                "accounts": GoogleAccountSerializer(accounts, many=True).data,
            }
        )
