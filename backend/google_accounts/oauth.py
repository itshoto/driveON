from django.conf import settings
from django.core import signing
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from google_auth_oauthlib.flow import Flow

STATE_SALT = "google-oauth-state"
STATE_MAX_AGE_SECONDS = 600

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
    Google's redirect back to /api/google/callback carries no auth header."""
    state = signing.dumps(user_id, salt=STATE_SALT)
    flow = _build_flow(state=state)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return auth_url


def resolve_state_to_user_id(state):
    return signing.loads(state, salt=STATE_SALT, max_age=STATE_MAX_AGE_SECONDS)


def exchange_code(code, state):
    """Exchanges the authorization code for tokens and resolves the
    connecting Google account's stable identity."""
    flow = _build_flow(state=state)
    flow.fetch_token(code=code)
    credentials = flow.credentials

    info = google_id_token.verify_oauth2_token(
        credentials.id_token, google_requests.Request(), settings.GOOGLE_OAUTH_CLIENT_ID
    )

    return {
        "credentials": credentials,
        "google_account_id": info["sub"],
        "email": info.get("email", ""),
        "display_name": info.get("name", ""),
    }
