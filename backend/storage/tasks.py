import hashlib
from io import BytesIO

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from accounts.client import get_client

from . import allocator
from .models import RebalanceRun


def _move_chunk(chunk, source_account, exclude):
    from accounts.models import StorageAccount
    from files.models import FileChunk

    sibling_ids = list(
        FileChunk.objects.filter(file_id=chunk.file_id, index=chunk.index)
        .exclude(id=chunk.id)
        .exclude(account__isnull=True)
        .values_list("account_id", flat=True)
    )
    exclude_accounts = list(StorageAccount.objects.filter(id__in=[a.id for a in exclude] + sibling_ids))

    destination = allocator.pick_rebalance_destination(chunk, exclude=exclude_accounts)
    if destination is None:
        raise RuntimeError("No valid rebalance destination available for this chunk.")

    data = b"".join(get_client(source_account).download_file_stream(chunk.google_file_id))
    if hashlib.sha256(data).hexdigest() != chunk.checksum:
        # Never touch the source over unverified data.
        raise ValueError("Downloaded chunk failed checksum verification; not moving.")

    result = get_client(destination).upload_file_streaming(
        BytesIO(data),
        f"{chunk.file.name}.part{chunk.index}.r{chunk.replica_number}",
        "application/octet-stream",
    )

    try:
        get_client(source_account).delete_file(chunk.google_file_id)
    except Exception:
        pass  # Best-effort cleanup -- the chunk record below now points at the verified new copy regardless.

    chunk.account = destination
    chunk.google_file_id = result["id"]
    chunk.save(update_fields=["account", "google_file_id", "updated_at"])

    source_account.storage_used = max(source_account.storage_used - chunk.size, 0)
    source_account.save(update_fields=["storage_used", "updated_at"])
    destination.storage_used += chunk.size
    destination.save(update_fields=["storage_used", "updated_at"])


@shared_task
def rebalance_user(run_id):
    """Moves chunks off the fullest connected account onto better-scoring
    ones until the imbalance clears or a safety cap is hit. Self-limiting
    and idempotent to re-trigger: each run re-checks imbalance before
    every move, so it never overshoots or fights a concurrent run."""
    from accounts.models import StorageAccount
    from files.models import FileChunk

    run = RebalanceRun.objects.select_related("user").get(id=run_id)
    try:
        check = allocator.check_imbalance(run.user)
        if not check["imbalanced"]:
            run.status = RebalanceRun.STATUS_COMPLETED
            return

        fullest = StorageAccount.objects.get(id=check["fullest_account"]["id"])
        candidates = list(
            FileChunk.objects.filter(account=fullest, status=FileChunk.STATUS_AVAILABLE)
            .select_related("file")
            .order_by("size")[: settings.REBALANCE_MAX_CHUNKS_PER_RUN]
        )
        run.chunks_planned = len(candidates)
        run.save(update_fields=["chunks_planned"])

        for chunk in candidates:
            if not allocator.check_imbalance(run.user)["imbalanced"]:
                break  # fixed already -- safe to stop; a later trigger handles any remainder
            try:
                _move_chunk(chunk, source_account=fullest, exclude=[fullest])
                run.chunks_moved += 1
            except Exception:
                run.errors_count += 1
            run.save(update_fields=["chunks_moved", "errors_count"])

        run.status = RebalanceRun.STATUS_COMPLETED
    except Exception:
        run.status = RebalanceRun.STATUS_FAILED
    finally:
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "finished_at"])

    from notifications.models import Notification
    from notifications.service import notify

    if run.status == RebalanceRun.STATUS_FAILED:
        notify(
            run.user, category=Notification.CATEGORY_REBALANCE, level=Notification.LEVEL_CRITICAL,
            title="Storage rebalancing failed",
            body="Rebalancing your connected accounts hit an error; your files are unaffected.",
            link="/drives", send_email=True,
        )
    elif run.chunks_moved > 0:
        notify(
            run.user, category=Notification.CATEGORY_REBALANCE, level=Notification.LEVEL_INFO,
            title="Storage rebalancing completed",
            body=f"Moved {run.chunks_moved} chunk(s) to better-balanced accounts.",
            link="/drives", send_email=False,
        )
    # chunks_moved == 0 and not failed -> imbalance resolved itself, or
    # there was nothing to move; nothing worth notifying about.
