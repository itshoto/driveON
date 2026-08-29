"""Single source of truth for a DriveFile's health: derived live from its
FileChunk rows, never stored, so it can't drift out of sync with chunk
state. Used by the serializer, the upload-status endpoint, and the
account-disconnect / rebalancing logic in files.views and
accounts.views."""

from dataclasses import dataclass

from accounts.models import StorageAccount

from .models import DriveFile, FileChunk

STATUS_HEALTHY = "healthy"
STATUS_AT_RISK = "at_risk"
STATUS_UNAVAILABLE = "unavailable"


@dataclass
class FileHealth:
    status: str
    chunks_available: int
    chunks_total: int
    redundancy_degraded: bool


def _group_by_index(chunks):
    by_index = {}
    for chunk in chunks:
        by_index.setdefault(chunk.index, []).append(chunk)
    return by_index


def _is_reachable(chunk):
    return (
        chunk.status == FileChunk.STATUS_AVAILABLE
        and chunk.account is not None
        and chunk.account.status == StorageAccount.STATUS_CONNECTED
    )


def compute_health(drive_file, chunks=None):
    """`chunks` lets callers pass an already-fetched list/queryset (e.g.
    prefetched across a whole file list) to avoid N+1 queries; falls back
    to fetching this file's chunks itself otherwise."""
    rows = list(chunks) if chunks is not None else list(
        drive_file.chunks.select_related("account")
    )

    if not rows:
        # No chunks yet -- upload hasn't produced any, or is still running.
        return FileHealth(STATUS_UNAVAILABLE, chunks_available=0, chunks_total=0, redundancy_degraded=False)

    by_index = _group_by_index(rows)
    chunks_total = len(by_index)
    chunks_available = 0
    redundancy_degraded = False
    fragile = False  # a non-redundant chunk sitting on a currently-erroring account

    for replicas in by_index.values():
        available = [r for r in replicas if _is_reachable(r)]
        if available:
            chunks_available += 1
        if len(available) < len(replicas):
            redundancy_degraded = True
        if len(replicas) == 1 and available and available[0].account.consecutive_errors > 0:
            fragile = True

    if chunks_available < chunks_total:
        status = STATUS_UNAVAILABLE
    elif redundancy_degraded or fragile:
        status = STATUS_AT_RISK
    else:
        status = STATUS_HEALTHY

    return FileHealth(status, chunks_available, chunks_total, redundancy_degraded)


def recompute_status(drive_file, chunks=None):
    """Maps live health back onto DriveFile.status. Healthy/at_risk both
    mean "fully downloadable right now" so both roll up to AVAILABLE --
    the finer-grained warning is what the `health` field is for. When
    unavailable, distinguishes FAILED (a block never successfully
    uploaded anywhere -- re-upload is the only fix) from
    PARTIALLY_AVAILABLE (every replica of some block sits on a currently
    *disconnected* account -- recoverable if that account reconnects)."""
    rows = list(chunks) if chunks is not None else list(
        drive_file.chunks.select_related("account")
    )

    if compute_health(drive_file, chunks=rows).status != STATUS_UNAVAILABLE:
        return DriveFile.STATUS_AVAILABLE

    for replicas in _group_by_index(rows).values():
        if any(_is_reachable(r) for r in replicas):
            continue
        if all(r.status == FileChunk.STATUS_FAILED for r in replicas):
            return DriveFile.STATUS_FAILED

    return DriveFile.STATUS_PARTIALLY_AVAILABLE
