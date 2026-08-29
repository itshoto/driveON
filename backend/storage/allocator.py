from django.conf import settings
from django.utils import timezone


class InsufficientStorageError(Exception):
    def __init__(self, required, available):
        self.required = required
        self.available = available
        super().__init__(f"Required {required} bytes, only {available} available")


def _connected_accounts(user):
    from accounts.models import StorageAccount

    return list(StorageAccount.objects.filter(user=user, status=StorageAccount.STATUS_CONNECTED))


def _refresh_all_quotas(accounts):
    """Quota can change on the provider's side outside driveON, so
    re-check before making placement decisions. Best-effort: an account
    that fails to respond keeps its last-known quota rather than aborting
    the whole operation (same tolerate-failure pattern as the rest of this
    app)."""
    from accounts.client import get_client

    for account in accounts:
        try:
            total, used = get_client(account).refresh_quota()
            account.storage_total = total
            account.storage_used = used
            account.quota_checked_at = timezone.now()
            account.save(update_fields=["storage_total", "storage_used", "quota_checked_at", "updated_at"])
        except Exception:
            pass


def check_capacity(user, required_bytes):
    """Sums free space across *all* connected accounts rather than
    requiring one account to fit everything -- the fix for driveON
    rejecting a file that no single account could hold even when the
    combined free space across accounts would cover it."""
    accounts = _connected_accounts(user)
    if not accounts:
        raise InsufficientStorageError(required_bytes, 0)
    _refresh_all_quotas(accounts)
    total_available = sum(a.storage_available for a in accounts)
    if total_available < required_bytes:
        raise InsufficientStorageError(required_bytes, total_available)


def _score(account, *, free_bytes, storage_total, max_speed, chunks_assigned_this_file, num_chunks, in_flight_others):
    """Weighted score used to rank candidate accounts for one chunk
    placement. Capacity dominates (0.4) since fitting the file at all is
    priority #1; reliability is next (0.3) since a flaky account directly
    hurts the file's health score; speed is a soft signal (0.2) that
    defaults neutral until an account has been observed; load (0.1) is a
    small corrective term so one file's chunks don't all pile onto one
    account."""
    free_ratio = 0.0 if storage_total <= 0 else max(0.0, min(1.0, free_bytes / storage_total))
    reliability = 1.0 / (1 + account.consecutive_errors)
    speed = 0.5 if not account.avg_throughput_bps else min(1.0, account.avg_throughput_bps / max_speed)
    load = min(1.0, (chunks_assigned_this_file / max(1, num_chunks)) + 0.1 * in_flight_others)
    return 0.4 * free_ratio + 0.3 * reliability + 0.2 * speed - 0.1 * load


def _uploading_count(account):
    from files.models import FileChunk

    return FileChunk.objects.filter(account=account, status=FileChunk.STATUS_UPLOADING).count()


def plan_allocation(user, num_chunks, chunk_size, replicas_per_chunk):
    """Returns list[num_chunks][replicas_per_chunk] of StorageAccount picks
    for one file's upload. Each replica of a given logical index lands on
    a distinct account. Capacity is checked and reserved per-chunk (not
    per-whole-file), so a file can spread across accounts none of which
    individually holds it all."""
    accounts = _connected_accounts(user)
    if replicas_per_chunk > len(accounts):
        raise ValueError(
            f"This redundancy level needs at least {replicas_per_chunk} connected "
            f"account(s); you have {len(accounts)}."
        )
    _refresh_all_quotas(accounts)

    max_speed = max((a.avg_throughput_bps or 0.0) for a in accounts) or 1.0
    reserved = {a.id: 0 for a in accounts}
    assigned_this_file = {a.id: 0 for a in accounts}
    in_flight = {a.id: _uploading_count(a) for a in accounts}

    plan = []
    for _index in range(num_chunks):
        used_for_this_index = set()
        replica_accounts = []
        for _replica in range(replicas_per_chunk):
            candidates = [
                a for a in accounts
                if a.id not in used_for_this_index and (a.storage_available - reserved[a.id]) >= chunk_size
            ]
            if not candidates:
                total_free = sum(max(a.storage_available - reserved[a.id], 0) for a in accounts)
                raise InsufficientStorageError(chunk_size, total_free)

            best = max(
                candidates,
                key=lambda a: (
                    _score(
                        a,
                        free_bytes=a.storage_available - reserved[a.id],
                        storage_total=a.storage_total,
                        max_speed=max_speed,
                        chunks_assigned_this_file=assigned_this_file[a.id],
                        num_chunks=num_chunks,
                        in_flight_others=in_flight[a.id],
                    ),
                    -assigned_this_file[a.id],
                    -a.id,
                ),
            )
            reserved[best.id] += chunk_size
            assigned_this_file[best.id] += 1
            used_for_this_index.add(best.id)
            replica_accounts.append(best)
        plan.append(replica_accounts)
    return plan


def reassign_failed_chunk(chunk, exclude):
    """Picks a replacement account for one chunk that failed to upload,
    excluding accounts already known bad for it (the account that just
    failed, plus any account already holding a sibling replica of the
    same logical index)."""
    exclude_ids = {a.id for a in exclude}
    accounts = [a for a in _connected_accounts(chunk.file.user) if a.id not in exclude_ids]
    if not accounts:
        return None
    _refresh_all_quotas(accounts)

    candidates = [a for a in accounts if a.storage_available >= chunk.size]
    if not candidates:
        return None

    max_speed = max((a.avg_throughput_bps or 0.0) for a in accounts) or 1.0
    return max(
        candidates,
        key=lambda a: _score(
            a,
            free_bytes=a.storage_available,
            storage_total=a.storage_total,
            max_speed=max_speed,
            chunks_assigned_this_file=0,
            num_chunks=1,
            in_flight_others=_uploading_count(a),
        ),
    )


# Rebalancing picks a destination with the same scoring function used for
# placement/retry -- it naturally favors the emptiest, most reliable
# valid account, which is exactly what moving a chunk *off* an overfull
# one should do.
pick_rebalance_destination = reassign_failed_chunk


def _account_summary(account, usage_ratio):
    return {
        "id": account.id,
        "email": account.email,
        "usage_ratio": round(usage_ratio, 4),
        "storage_used": account.storage_used,
        "storage_total": account.storage_total,
    }


def check_imbalance(user):
    """Flags a fullest-vs-emptiest usage gap worth acting on. Requires the
    fullest account to actually be meaningfully full (>60%) so two
    near-empty accounts that merely differ by the threshold don't trigger
    a pointless "rebalance" prompt."""
    accounts = _connected_accounts(user)
    if len(accounts) < 2:
        return {"imbalanced": False}
    _refresh_all_quotas(accounts)

    ratios = [(a, (a.storage_used / a.storage_total) if a.storage_total else 0.0) for a in accounts]
    fullest_account, fullest_ratio = max(ratios, key=lambda pair: pair[1])
    emptiest_account, emptiest_ratio = min(ratios, key=lambda pair: pair[1])
    delta = fullest_ratio - emptiest_ratio

    return {
        "imbalanced": delta > settings.REBALANCE_IMBALANCE_THRESHOLD and fullest_ratio > 0.6,
        "delta": round(delta, 4),
        "fullest_account": _account_summary(fullest_account, fullest_ratio),
        "emptiest_account": _account_summary(emptiest_account, emptiest_ratio),
    }
