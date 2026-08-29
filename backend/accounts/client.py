from .clients.google_drive import GoogleDriveClient
from .clients.google_drive import revoke_refresh_token as _revoke_google
from .clients.onedrive import OneDriveClient
from .clients.onedrive import revoke_refresh_token as _revoke_microsoft
from .models import StorageAccount

_CLIENTS = {
    StorageAccount.PROVIDER_GOOGLE: GoogleDriveClient,
    StorageAccount.PROVIDER_MICROSOFT: OneDriveClient,
}

_REVOKERS = {
    StorageAccount.PROVIDER_GOOGLE: _revoke_google,
    StorageAccount.PROVIDER_MICROSOFT: _revoke_microsoft,
}


def get_client(account):
    """Returns the right provider client for `account`. Every call site
    that used to instantiate DriveService(account) directly now calls
    this instead -- the rest of the codebase never branches on provider."""
    try:
        client_cls = _CLIENTS[account.provider]
    except KeyError:
        raise ValueError(f"Unknown storage provider: {account.provider}")
    return client_cls(account)


def revoke_refresh_token(account):
    """Best-effort revocation of a connected account's OAuth grant,
    dispatched to the right provider (see clients/google_drive.py and
    clients/onedrive.py for what "best-effort" means per provider)."""
    revoker = _REVOKERS.get(account.provider)
    if revoker:
        revoker(account)
