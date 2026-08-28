from firebase_admin import auth as firebase_auth
from rest_framework import authentication, exceptions

from .firebase import get_firebase_app
from .models import User


def verify_firebase_token(request):
    """Verify the Bearer token on `request` against Firebase and return
    the decoded token payload, or None if no token was supplied."""
    header = authentication.get_authorization_header(request).decode("utf-8")
    if not header or not header.startswith("Bearer "):
        return None

    id_token = header[len("Bearer ") :]
    get_firebase_app()
    try:
        return firebase_auth.verify_id_token(id_token)
    except Exception as exc:
        raise exceptions.AuthenticationFailed("Invalid or expired Firebase token") from exc


class FirebaseAuthentication(authentication.BaseAuthentication):
    """Maps a verified Firebase ID token to the matching local driveON
    User. Does NOT create the user -- new accounts must first call
    /api/auth/sync (see users.views.SyncView)."""

    def authenticate(self, request):
        decoded = verify_firebase_token(request)
        if decoded is None:
            return None

        firebase_uid = decoded.get("uid")
        if not firebase_uid:
            raise exceptions.AuthenticationFailed("Firebase token missing uid")

        try:
            user = User.objects.select_related("plan").get(
                firebase_uid=firebase_uid, is_active=True
            )
        except User.DoesNotExist as exc:
            raise exceptions.AuthenticationFailed(
                "No driveON account linked to this Firebase user. Call /api/auth/sync first."
            ) from exc

        return (user, None)
