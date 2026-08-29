import re
import time

from django.db import IntegrityError
from firebase_admin import auth as firebase_auth
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import verify_firebase_token
from .firebase import get_firebase_app
from .models import Plan, User
from .serializers import UserSerializer

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")

# Deleting the account is irreversible, so we require the Firebase token to
# come from a sign-in within this window rather than a silently-refreshed
# session -- see SOP section 8 (same "prove you are you" bar as unlinking a
# Google account, but higher stakes since this also removes the profile).
ACCOUNT_DELETION_REAUTH_WINDOW_SECONDS = 5 * 60
ACCOUNT_DELETION_CONFIRMATION_PHRASE = "DELETE"


class SyncView(APIView):
    """Called by the frontend immediately after Firebase sign-up/sign-in.

    Creates the local driveON profile on first call (registration) and
    simply returns it on subsequent calls (login). This view intentionally
    bypasses FirebaseAuthentication, since on first call no local User row
    exists yet to authenticate against.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        decoded = verify_firebase_token(request)
        if decoded is None:
            return Response(
                {"detail": "Missing or invalid Authorization header."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        firebase_uid = decoded["uid"]
        firebase_email = decoded.get("email", "")

        try:
            user = User.objects.get(firebase_uid=firebase_uid)
            return Response(UserSerializer(user).data)
        except User.DoesNotExist:
            pass

        username = (request.data.get("username") or "").strip()
        if not username:
            return Response(
                {"detail": "username is required to complete registration."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not USERNAME_RE.match(username):
            return Response(
                {
                    "detail": "username must be 3-32 characters: letters, numbers, underscore only."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.create_user(
                firebase_uid=firebase_uid,
                username=username,
                email=firebase_email,
                plan=Plan.get_default_plan(),
            )
        except IntegrityError:
            return Response(
                {"detail": "That username or email is already taken."},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def delete(self, request):
        """Permanently deletes the caller's driveON account. Best-effort
        revokes every connected storage account's token, deletes the local
        profile (cascading to StorageAccount and DriveFile rows), then
        deletes the Firebase Auth user so this credential can never sign
        back in as this account. Irreversible -- gated behind a recent
        sign-in and an explicit confirmation phrase.
        """
        from accounts.client import revoke_refresh_token
        from accounts.models import StorageAccount

        decoded = request.auth or {}
        auth_time = decoded.get("auth_time")
        if not auth_time or (time.time() - auth_time) > ACCOUNT_DELETION_REAUTH_WINDOW_SECONDS:
            return Response(
                {
                    "detail": "For your security, please sign in again before deleting your account.",
                    "code": "reauth_required",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if request.data.get("confirmation") != ACCOUNT_DELETION_CONFIRMATION_PHRASE:
            return Response(
                {"detail": f'Type "{ACCOUNT_DELETION_CONFIRMATION_PHRASE}" to confirm account deletion.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        firebase_uid = user.firebase_uid

        for account in StorageAccount.objects.filter(user=user, status=StorageAccount.STATUS_CONNECTED):
            revoke_refresh_token(account)

        user.delete()  # Cascades to this user's StorageAccount and DriveFile rows.

        try:
            get_firebase_app()
            firebase_auth.delete_user(firebase_uid)
        except Exception:
            pass  # The driveON account is already gone; Firebase cleanup is best-effort.

        return Response(status=status.HTTP_204_NO_CONTENT)
