from datetime import timedelta
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.utils import timezone

from .state import build_state

AUTHORIZE_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
GRAPH_ME_URL = "https://graph.microsoft.com/v1.0/me"


def build_authorization_url(user_id):
    """Builds the Microsoft consent URL. `state` binds this OAuth flow to
    the driveON user that initiated it, same as the Google flow -- Google's
    and Microsoft's redirects both carry no auth header."""
    state = build_state(user_id, "microsoft")
    params = {
        "client_id": settings.MICROSOFT_OAUTH_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": settings.MICROSOFT_OAUTH_REDIRECT_URI,
        "response_mode": "query",
        "scope": " ".join(settings.MICROSOFT_OAUTH_SCOPES),
        "state": state,
        "prompt": "consent",
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code(code, state):
    """Exchanges the authorization code for tokens and resolves the
    connecting Microsoft account's stable identity. Returns the same
    provider-agnostic shape as oauth.google.exchange_code so CallbackView
    never needs to branch on provider."""
    token_resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": settings.MICROSOFT_OAUTH_CLIENT_ID,
            "client_secret": settings.MICROSOFT_OAUTH_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.MICROSOFT_OAUTH_REDIRECT_URI,
            "scope": " ".join(settings.MICROSOFT_OAUTH_SCOPES),
        },
        timeout=10,
    )
    token_resp.raise_for_status()
    tokens = token_resp.json()

    profile_resp = requests.get(
        GRAPH_ME_URL, headers={"Authorization": f"Bearer {tokens['access_token']}"}, timeout=10
    )
    profile_resp.raise_for_status()
    profile = profile_resp.json()

    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", ""),
        "token_expiry": timezone.now() + timedelta(seconds=tokens.get("expires_in", 3600)),
        "provider_account_id": profile["id"],
        "email": profile.get("mail") or profile.get("userPrincipalName", ""),
        "display_name": profile.get("displayName", ""),
    }
