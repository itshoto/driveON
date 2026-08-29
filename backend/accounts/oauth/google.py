from datetime import timezone as dt_timezone

from django.conf import settings
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from google_auth_oauthlib.flow import Flow

from .state import build_state

# `drive` (not `drive.file`) is required because driveON must create and
# manage chunk files it did not itself create the picker for, and must be
# able to enumerate the user's existing files for the unified browser --
# see SOP section 45.
EXTRA_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]


def _client_config():
    return {
        "web": {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.GOOGLE_OAUTH_REDIRECT_URI],
        }
    }


def _build_flow(state=None):
    flow = Flow.from_client_config(
        _client_config(),
        scopes=EXTRA_SCOPES + settings.GOOGLE_OAUTH_SCOPES,
        state=state,
    )
    flow.redirect_uri = settings.GOOGLE_OAUTH_REDIRECT_URI
    return flow


def build_authorization_url(user_id):
    """Builds the Google consent URL. `state` is a signed, expiring token
    binding this OAuth flow to the driveON user that initiated it, since
    Google's redirect back to /api/accounts/callback/google carries no
    auth header."""
    state = build_state(user_id, "google")
    flow = _build_flow(state=state)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return auth_url


def exchange_code(code, state):
    """Exchanges the authorization code for tokens and resolves the
    connecting Google account's stable identity. Returns the same
    provider-agnostic shape as oauth.microsoft.exchange_code so
    CallbackView never needs to branch on provider."""
    flow = _build_flow(state=state)
    flow.fetch_token(code=code)
    credentials = flow.credentials

    info = google_id_token.verify_oauth2_token(
        credentials.id_token, google_requests.Request(), settings.GOOGLE_OAUTH_CLIENT_ID
    )

    # google-auth's Credentials.expiry is naive UTC; store it aware like
    # everywhere else in this codebase (USE_TZ=True).
    expiry = credentials.expiry
    if expiry is not None and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=dt_timezone.utc)

    return {
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_expiry": expiry,
        "provider_account_id": info["sub"],
        "email": info.get("email", ""),
        "display_name": info.get("name", ""),
    }
