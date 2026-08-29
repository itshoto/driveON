from django.conf import settings
from django.core import signing
from django.shortcuts import redirect
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import User

from .client import get_client, revoke_refresh_token
from .encryption import encrypt_token
from .models import StorageAccount
from .oauth import google as oauth_google
from .oauth import microsoft as oauth_microsoft
from .oauth.state import resolve_state
from .serializers import StorageAccountSerializer

OAUTH_MODULES = {
    StorageAccount.PROVIDER_GOOGLE: oauth_google,
    StorageAccount.PROVIDER_MICROSOFT: oauth_microsoft,
}


class ConnectView(APIView):
    """Starts the OAuth flow for the currently logged-in driveON user
    against the given provider ("google" or "microsoft")."""

    permission_classes = [IsAuthenticated]

    def get(self, request, provider):
        oauth_module = OAUTH_MODULES.get(provider)
        if oauth_module is None:
            return Response({"detail": "Unknown provider."}, status=status.HTTP_400_BAD_REQUEST)

        if (
            StorageAccount.objects.filter(user=request.user, status=StorageAccount.STATUS_CONNECTED).count()
            >= request.user.max_connected_accounts()
        ):
            return Response(
                {"detail": "Maximum connected accounts reached for your plan."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response({"authorization_url": oauth_module.build_authorization_url(request.user.id)})


class CallbackView(APIView):
    """The provider redirects the user's browser here after consent. There
    is no Authorization header on this request, so the driveON user (and
    which provider this is) is recovered from the signed `state` parameter
    instead of FirebaseAuthentication."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, provider):
        def fail(reason):
            return redirect(f"{settings.FRONTEND_URL}/drives?error={reason}")

        oauth_module = OAUTH_MODULES.get(provider)
        if oauth_module is None:
            return fail("invalid_request")

        if request.query_params.get("error"):
            return fail("access_denied")

        code = request.query_params.get("code")
        state = request.query_params.get("state")
        if not code or not state:
            return fail("invalid_request")

        try:
            user_id, state_provider = resolve_state(state)
            if state_provider != provider:
                return fail("invalid_state")
            user = User.objects.select_related("plan").get(id=user_id)
        except (signing.BadSignature, User.DoesNotExist):
            return fail("invalid_state")

        try:
            result = oauth_module.exchange_code(code, state)
        except Exception:
            return fail("oauth_failed")

        provider_account_id = result["provider_account_id"]

        # One provider account can only ever belong to one driveON user --
        # this is the core anti-duplicate rule (SOP section 8). We reveal
        # nothing about who owns it, only that it's taken.
        existing = StorageAccount.objects.filter(
            provider=provider, provider_account_id=provider_account_id
        ).first()
        if existing and existing.user_id != user.id:
            return fail("already_connected")

        already_active = existing is not None and existing.status == StorageAccount.STATUS_CONNECTED
        if not already_active:
            active_count = StorageAccount.objects.filter(
                user=user, status=StorageAccount.STATUS_CONNECTED
            ).count()
            if active_count >= user.max_connected_accounts():
                return fail("max_accounts_reached")

        refresh_token = result["refresh_token"]
        if not refresh_token and not (existing and existing.encrypted_refresh_token):
            # Both providers only reliably issue a refresh_token on a
            # fresh consent; without one we can't do offline (background)
            # access.
            return fail("missing_refresh_token")

        account, _ = StorageAccount.objects.update_or_create(
            provider=provider,
            provider_account_id=provider_account_id,
            defaults={
                "user": user,
                "email": result["email"],
                "display_name": result["display_name"],
                "encrypted_access_token": encrypt_token(result["access_token"]),
                "encrypted_refresh_token": (
                    encrypt_token(refresh_token) if refresh_token else existing.encrypted_refresh_token
                ),
                "token_expiry": result["token_expiry"],
                "status": StorageAccount.STATUS_CONNECTED,
            },
        )

        try:
            total, used = get_client(account).refresh_quota()
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
        accounts = StorageAccount.objects.filter(user=request.user).order_by("created_at")
        return Response(StorageAccountSerializer(accounts, many=True).data)


class AccountDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, account_id):
        # Local imports: files depends on accounts, not vice versa.
        from files.health import recompute_status
        from files.models import DriveFile, FileChunk
        from notifications.models import Notification
        from notifications.service import notify

        try:
            account = StorageAccount.objects.get(id=account_id, user=request.user)
        except StorageAccount.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        affected_file_ids = list(
            FileChunk.objects.filter(account=account, status=FileChunk.STATUS_AVAILABLE)
            .values_list("file_id", flat=True)
            .distinct()
        )

        if affected_file_ids and request.query_params.get("force") != "true":
            return Response(
                {
                    "detail": (
                        f"This account contains data belonging to {len(affected_file_ids)} driveON file(s). "
                        "Removing it may make those files unavailable until the account is reconnected."
                    ),
                    "dependent_files": len(affected_file_ids),
                    "requires_confirmation": True,
                },
                status=status.HTTP_409_CONFLICT,
            )

        revoke_refresh_token(account)  # Best-effort; token is deleted from our DB regardless.

        account.status = StorageAccount.STATUS_DISCONNECTED
        account.encrypted_access_token = ""
        account.encrypted_refresh_token = ""
        account.save(
            update_fields=["status", "encrypted_access_token", "encrypted_refresh_token", "updated_at"]
        )

        # Recompute each affected file's status now that this account is
        # disconnected -- a file with healthy replicas elsewhere may still
        # be fully available, so this must never be a blanket downgrade.
        # Tally the *actual* outcome (not the pre-disconnect count above)
        # since recompute_status is specifically designed to let a file
        # stay AVAILABLE when it has redundancy elsewhere.
        affected_files = DriveFile.objects.filter(id__in=affected_file_ids).prefetch_related(
            "chunks", "chunks__account"
        )
        failed_count = degraded_count = still_available_count = 0
        for drive_file in affected_files:
            new_status = recompute_status(drive_file, chunks=drive_file.chunks.all())
            drive_file.status = new_status
            drive_file.save(update_fields=["status", "updated_at"])
            if new_status == DriveFile.STATUS_FAILED:
                failed_count += 1
            elif new_status != DriveFile.STATUS_AVAILABLE:
                degraded_count += 1
            else:
                still_available_count += 1

        if failed_count or degraded_count:
            parts = []
            if failed_count:
                parts.append(f"{failed_count} file(s) are now unavailable")
            if degraded_count:
                parts.append(f"{degraded_count} file(s) are now partially available")
            if still_available_count:
                parts.append(f"{still_available_count} file(s) stayed fully available thanks to redundancy")

            notify(
                request.user,
                category=Notification.CATEGORY_ACCOUNT,
                level=Notification.LEVEL_CRITICAL if failed_count else Notification.LEVEL_WARNING,
                title=f"Disconnected {account.email}",
                body="; ".join(parts).capitalize() + ".",
                link="/files",
                send_email=True,
            )

        return Response(StorageAccountSerializer(account).data)
