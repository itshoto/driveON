from django.utils import timezone


class InsufficientStorageError(Exception):
    def __init__(self, required, available):
        self.required = required
        self.available = available
        super().__init__(f"Required {required} bytes, only {available} available")


def select_account_for_file(user, file_size):
    """Phase 2 (non-distributed) allocation: pick the connected account
    with the least free space that can still fit the whole file
    (best-fit). Quota is refreshed first since usage on Google's side can
    change outside driveON -- see SOP sections 26 and 67."""
    from google_accounts.client import DriveService
    from google_accounts.models import GoogleAccount

    accounts = list(
        GoogleAccount.objects.filter(user=user, status=GoogleAccount.STATUS_CONNECTED)
    )
    if not accounts:
        raise InsufficientStorageError(file_size, 0)

    candidates = []
    total_available = 0
    for account in accounts:
        try:
            total, used = DriveService(account).refresh_quota()
            account.storage_total = total
            account.storage_used = used
            account.quota_checked_at = timezone.now()
            account.save(update_fields=["storage_total", "storage_used", "quota_checked_at", "updated_at"])
        except Exception:
            pass  # fall back to last-known quota rather than failing the upload
        total_available += account.storage_available
        if account.storage_available >= file_size:
            candidates.append(account)

    if not candidates:
        raise InsufficientStorageError(file_size, total_available)

    return min(candidates, key=lambda a: a.storage_available)
