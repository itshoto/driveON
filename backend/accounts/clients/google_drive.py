from datetime import timezone as dt_timezone
from functools import wraps
from io import BytesIO

import requests
from django.conf import settings
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from ..encryption import decrypt_token, encrypt_token

UPLOAD_CHUNK_SIZE = 8 * 1024 * 1024
DOWNLOAD_CHUNK_SIZE = 8 * 1024 * 1024


def _credentials_for_account(account):
    expiry = account.token_expiry
    if expiry is not None and expiry.tzinfo is not None:
        expiry = expiry.astimezone(dt_timezone.utc).replace(tzinfo=None)
    return Credentials(
        token=decrypt_token(account.encrypted_access_token),
        refresh_token=decrypt_token(account.encrypted_refresh_token),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
        client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
        expiry=expiry,
    )


def _persists_refreshed_token(method):
    """Google's client refreshes an expired access token transparently
    mid-request. Persist the new token back to the encrypted DB column
    afterwards so the next call doesn't have to refresh again."""

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        result = method(self, *args, **kwargs)
        self._persist_token_if_refreshed()
        return result

    return wrapper


class GoogleDriveClient:
    """Wraps the Google Drive API v3 client for one connected account.
    Keeps googleapiclient details out of views/tasks (SOP section 61)."""

    def __init__(self, account):
        self.account = account
        self.credentials = _credentials_for_account(account)
        self._service = build(
            "drive", "v3", credentials=self.credentials, cache_discovery=False
        )

    def _persist_token_if_refreshed(self):
        current = decrypt_token(self.account.encrypted_access_token)
        if self.credentials.token and self.credentials.token != current:
            self.account.encrypted_access_token = encrypt_token(self.credentials.token)
            if self.credentials.expiry:
                self.account.token_expiry = self.credentials.expiry.replace(
                    tzinfo=dt_timezone.utc
                )
            self.account.save(update_fields=["encrypted_access_token", "token_expiry", "updated_at"])

    @_persists_refreshed_token
    def refresh_quota(self):
        about = self._service.about().get(fields="storageQuota").execute()
        quota = about.get("storageQuota", {})
        total = int(quota.get("limit") or 0)
        used = int(quota.get("usage") or 0)
        return total, used

    @_persists_refreshed_token
    def upload_file_streaming(self, file_obj, filename, mime_type):
        """Uploads via Google's resumable upload protocol (SOP section 17),
        reading the source in fixed-size chunks instead of loading the
        whole file into memory."""
        media = MediaIoBaseUpload(
            file_obj, mimetype=mime_type, chunksize=UPLOAD_CHUNK_SIZE, resumable=True
        )
        request = self._service.files().create(
            body={"name": filename},
            media_body=media,
            fields="id,name,mimeType,size,md5Checksum",
        )
        response = None
        while response is None:
            _, response = request.next_chunk()
        return response

    def download_file_stream(self, file_id, chunk_size=DOWNLOAD_CHUNK_SIZE):
        """Yields the file content in chunks so callers can stream the
        response instead of buffering the whole file (SOP section 21)."""
        request = self._service.files().get_media(fileId=file_id)
        buffer = BytesIO()
        downloader = MediaIoBaseDownload(buffer, request, chunksize=chunk_size)
        done = False
        while not done:
            _, done = downloader.next_chunk()
            buffer.seek(0)
            yield buffer.read()
            buffer.seek(0)
            buffer.truncate(0)
        self._persist_token_if_refreshed()

    @_persists_refreshed_token
    def delete_file(self, file_id):
        self._service.files().delete(fileId=file_id).execute()


def revoke_refresh_token(account):
    """Best-effort revocation of a connected account's Google refresh
    token with Google, so driveON losing the token doesn't leave a
    standing grant behind. Safe to call even if the token is already
    invalid, expired, or missing."""
    try:
        refresh_token = decrypt_token(account.encrypted_refresh_token)
    except Exception:
        return
    if not refresh_token:
        return
    try:
        requests.post(
            "https://oauth2.googleapis.com/revoke",
            params={"token": refresh_token},
            timeout=5,
        )
    except Exception:
        pass
