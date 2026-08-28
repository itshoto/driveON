import re

from django.db import IntegrityError
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import verify_firebase_token
from .models import Plan, User
from .serializers import UserSerializer

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")


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
