import requests
from django.conf import settings
from django.core import signing
from django.shortcuts import redirect
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import User

from .client import DriveService
from .encryption import encrypt_token
from .models import GoogleAccount
from .oauth import build_authorization_url, exchange_code, resolve_state_to_user_id
from .serializers import GoogleAccountSerializer


class ConnectView(APIView):
    """Starts the OAuth flow for the currently logged-in driveON user."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if (
            GoogleAccount.objects.filter(
                user=request.user, status=GoogleAccount.STATUS_CONNECTED
            ).count()
            >= request.user.max_google_accounts()
        ):
            return Response(
                {"detail": "Maximum Google accounts reached for your plan."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response({"authorization_url": build_authorization_url(request.user.id)})


class CallbackView(APIView):
    """Google redirects the user's browser here after consent. There is no
    Authorization header on this request, so the driveON user is recovered
    from the signed `state` parameter instead of FirebaseAuthentication."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        def fail(reason):
            return redirect(f"{settings.FRONTEND_URL}/drives?error={reason}")

        if request.query_params.get("error"):
            return fail("access_denied")

        code = request.query_params.get("code")
        state = request.query_params.get("state")
        if not code or not state:
            return fail("invalid_request")

        try:
            user_id = resolve_state_to_user_id(state)
            user = User.objects.select_related("plan").get(id=user_id)
        except (signing.BadSignature, User.DoesNotExist):
            return fail("invalid_state")

        try:
            result = exchange_code(code, state)
        except Exception:
            return fail("oauth_failed")

        google_account_id = result["google_account_id"]
        credentials = result["credentials"]

        # One Google account can only ever belong to one driveON user --
        # this is the core anti-duplicate rule (SOP section 8). We reveal
        # nothing about who owns it, only that it's taken.
        existing = GoogleAccount.objects.filter(google_account_id=google_account_id).first()
        if existing and existing.user_id != user.id:
            return fail("already_connected")

        already_active = existing is not None and existing.status == GoogleAccount.STATUS_CONNECTED
        if not already_active:
            active_count = GoogleAccount.objects.filter(
                user=user, status=GoogleAccount.STATUS_CONNECTED
            ).count()
            if active_count >= user.max_google_accounts():
                return fail("max_accounts_reached")

        refresh_token = credentials.refresh_token
        if not refresh_token and not (existing and existing.encrypted_refresh_token):
            # Google only issues a refresh_token on the first-ever consent
            # for this client+account pair; without one we can't do
            # offline (background) access.
            return fail("missing_refresh_token")

        account, _ = GoogleAccount.objects.update_or_create(
            google_account_id=google_account_id,
            defaults={
                "user": user,
                "email": result["email"],
                "display_name": result["display_name"],
                "encrypted_access_token": encrypt_token(credentials.token),
                "encrypted_refresh_token": (
                    encrypt_token(refresh_token) if refresh_token else existing.encrypted_refresh_token
                ),
                "status": GoogleAccount.STATUS_CONNECTED,
            },
        )

        try:
            drive = DriveService(account)
            total, used = drive.refresh_quota()
            account.storage_total = total
            account.storage_used = used
            account.quota_checked_at = timezone.now()
            account.save(update_fields=["storage_total", "storage_used", "quota_checked_at"])
        except Exception:
            pass  # Non-fatal: quota will be refreshed on next dashboard load.

        return redirect(f"{settings.FRONTEND_URL}/drives?connected=1")


class AccountListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        accounts = GoogleAccount.objects.filter(user=request.user).order_by("created_at")
        return Response(GoogleAccountSerializer(accounts, many=True).data)


class AccountDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, account_id):
        from files.models import DriveFile  # local import: files depends on google_accounts, not vice versa

        try:
            account = GoogleAccount.objects.get(id=account_id, user=request.user)
        except GoogleAccount.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        dependent_files = DriveFile.objects.filter(
            google_account=account, status__in=[DriveFile.STATUS_AVAILABLE, DriveFile.STATUS_PARTIALLY_AVAILABLE]
        )
        dependent_count = dependent_files.count()

        if dependent_count and request.query_params.get("force") != "true":
            return Response(
                {
                    "detail": (
                        f"This account contains data belonging to {dependent_count} driveON file(s). "
                        "Removing it may make those files unavailable until the account is reconnected."
                    ),
                    "dependent_files": dependent_count,
                    "requires_confirmation": True,
                },
                status=status.HTTP_409_CONFLICT,
            )

        try:
            refresh_token = DriveService(account).credentials.refresh_token
            if refresh_token:
                requests.post(
                    "https://oauth2.googleapis.com/revoke",
                    params={"token": refresh_token},
                    timeout=5,
                )
        except Exception:
            pass  # Best-effort revoke; token is deleted from our DB regardless.

        dependent_files.update(status=DriveFile.STATUS_PARTIALLY_AVAILABLE)

        account.status = GoogleAccount.STATUS_DISCONNECTED
        account.encrypted_access_token = ""
        account.encrypted_refresh_token = ""
        account.save(
            update_fields=["status", "encrypted_access_token", "encrypted_refresh_token", "updated_at"]
        )

        return Response(GoogleAccountSerializer(account).data)
