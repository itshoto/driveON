from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

from ..encryption import decrypt_token, encrypt_token

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
UPLOAD_FOLDER = "driveON"
DOWNLOAD_CHUNK_SIZE = 8 * 1024 * 1024


class OneDriveClient:
    """Wraps the Microsoft Graph API for one connected OneDrive account.
    Mirrors GoogleDriveClient's interface (refresh_quota,
    upload_file_streaming, download_file_stream, delete_file) so callers
    never need to know which provider they're talking to."""

    def __init__(self, account):
        self.account = account

    def _ensure_fresh_token(self):
        # Unlike Google's SDK (which refreshes transparently mid-request),
        # Graph access tokens must be refreshed explicitly before use.
        expiry = self.account.token_expiry
        if expiry and expiry > timezone.now() + timedelta(minutes=2):
            return
        self._refresh_access_token()

    def _refresh_access_token(self):
        refresh_token = decrypt_token(self.account.encrypted_refresh_token)
        response = requests.post(
            TOKEN_URL,
            data={
                "client_id": settings.MICROSOFT_OAUTH_CLIENT_ID,
                "client_secret": settings.MICROSOFT_OAUTH_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "scope": " ".join(settings.MICROSOFT_OAUTH_SCOPES),
            },
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()

        self.account.encrypted_access_token = encrypt_token(payload["access_token"])
        if payload.get("refresh_token"):
            self.account.encrypted_refresh_token = encrypt_token(payload["refresh_token"])
        self.account.token_expiry = timezone.now() + timedelta(seconds=payload.get("expires_in", 3600))
        self.account.save(
            update_fields=["encrypted_access_token", "encrypted_refresh_token", "token_expiry", "updated_at"]
        )

    def _headers(self):
        self._ensure_fresh_token()
        token = decrypt_token(self.account.encrypted_access_token)
        return {"Authorization": f"Bearer {token}"}

    def refresh_quota(self):
        resp = requests.get(f"{GRAPH_BASE}/me/drive", headers=self._headers(), timeout=10)
        resp.raise_for_status()
        quota = resp.json().get("quota", {})
        return int(quota.get("total") or 0), int(quota.get("used") or 0)

    def upload_file_streaming(self, file_obj, filename, mime_type):
        """Uploads via a Graph upload session -- the simple-PUT path caps
        at 4MB, below our 8MB block size, so a session is used uniformly
        even though each block already fits comfortably in memory."""
        session_resp = requests.post(
            f"{GRAPH_BASE}/me/drive/root:/{UPLOAD_FOLDER}/{filename}:/createUploadSession",
            headers=self._headers(),
            json={"item": {"@microsoft.graph.conflictBehavior": "replace"}},
            timeout=10,
        )
        session_resp.raise_for_status()
        upload_url = session_resp.json()["uploadUrl"]

        data = file_obj.read()
        put_resp = requests.put(
            upload_url,
            data=data,
            headers={
                "Content-Length": str(len(data)),
                "Content-Range": f"bytes 0-{len(data) - 1}/{len(data)}",
            },
            timeout=60,
        )
        put_resp.raise_for_status()
        return {"id": put_resp.json()["id"]}

    def download_file_stream(self, file_id, chunk_size=DOWNLOAD_CHUNK_SIZE):
        resp = requests.get(
            f"{GRAPH_BASE}/me/drive/items/{file_id}/content",
            headers=self._headers(),
            stream=True,
            timeout=60,
        )
        resp.raise_for_status()
        for block in resp.iter_content(chunk_size=chunk_size):
            if block:
                yield block

    def delete_file(self, file_id):
        resp = requests.delete(f"{GRAPH_BASE}/me/drive/items/{file_id}", headers=self._headers(), timeout=10)
        if resp.status_code not in (204, 404):
            resp.raise_for_status()


def revoke_refresh_token(account):
    """Microsoft's identity platform has no simple per-token REST revoke
    endpoint for this flow (unlike Google's /revoke) -- a standing grant
    can only be fully removed by the user via account.live.com/consent/Manage
    or an Azure AD admin action. Deleting the stored tokens (done by the
    caller regardless) is what actually stops driveON from using it; this
    is a documented no-op kept only so callers can treat both providers
    the same way."""
    return
