import hashlib
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from accounts.client import get_client
from storage import allocator

from . import health
from .models import DriveFile, FileChunk


def _sha256_of_file(path, block_size=1024 * 1024):
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(block_size)
            if not block:
                break
            hasher.update(block)
    return hasher.hexdigest()


def _chunk_len(total_size, chunk_size, index):
    return min(chunk_size, total_size - index * chunk_size)


def _record_transfer_result(account, *, success, bytes_transferred, elapsed):
    if success:
        account.consecutive_errors = 0
        if elapsed > 0:
            observed_bps = bytes_transferred / elapsed
            account.avg_throughput_bps = (
                observed_bps
                if account.avg_throughput_bps is None
                else 0.3 * observed_bps + 0.7 * account.avg_throughput_bps
            )
    else:
        account.consecutive_errors += 1
    account.save(update_fields=["consecutive_errors", "avg_throughput_bps", "updated_at"])


def _pick_retry_account(chunk, failed_account):
    from accounts.models import StorageAccount

    sibling_ids = list(
        FileChunk.objects.filter(file_id=chunk.file_id, index=chunk.index)
        .exclude(id=chunk.id)
        .exclude(account__isnull=True)
        .values_list("account_id", flat=True)
    )
    exclude = list(StorageAccount.objects.filter(id__in=[failed_account.id, *sibling_ids]))
    return allocator.reassign_failed_chunk(chunk, exclude=exclude)


def _upload_one_chunk(chunk_id, temp_path, mime_type, is_retry=False):
    chunk = FileChunk.objects.select_related("account", "file").get(id=chunk_id)
    account = chunk.account
    if account is None:
        chunk.status = FileChunk.STATUS_FAILED
        chunk.save(update_fields=["status", "updated_at"])
        return

    chunk.status = FileChunk.STATUS_UPLOADING
    chunk.upload_started_at = timezone.now()
    chunk.save(update_fields=["status", "upload_started_at", "updated_at"])

    with open(temp_path, "rb") as f:
        f.seek(chunk.index * chunk.file.chunk_size)
        data = f.read(chunk.size)

    started = time.monotonic()
    try:
        result = get_client(account).upload_file_streaming(
            BytesIO(data),
            f"{chunk.file.name}.part{chunk.index}.r{chunk.replica_number}",
            "application/octet-stream",
        )
    except Exception:
        _record_transfer_result(account, success=False, bytes_transferred=0, elapsed=time.monotonic() - started)

        if is_retry:
            chunk.status = FileChunk.STATUS_FAILED
            chunk.save(update_fields=["status", "updated_at"])
            return

        new_account = _pick_retry_account(chunk, failed_account=account)
        if new_account is None:
            chunk.status = FileChunk.STATUS_FAILED
            chunk.save(update_fields=["status", "updated_at"])
            return

        chunk.account = new_account
        chunk.status = FileChunk.STATUS_PENDING
        chunk.save(update_fields=["account", "status", "updated_at"])
        _upload_one_chunk(chunk_id, temp_path, mime_type, is_retry=True)
        return

    elapsed = time.monotonic() - started
    _record_transfer_result(account, success=True, bytes_transferred=len(data), elapsed=elapsed)

    chunk.google_file_id = result["id"]
    chunk.checksum = hashlib.sha256(data).hexdigest()
    chunk.bytes_transferred = len(data)
    chunk.status = FileChunk.STATUS_AVAILABLE
    chunk.upload_completed_at = timezone.now()
    chunk.save(
        update_fields=[
            "google_file_id", "checksum", "bytes_transferred", "status", "upload_completed_at", "updated_at",
        ]
    )

    account.storage_used += len(data)
    account.save(update_fields=["storage_used", "updated_at"])


@shared_task
def process_upload(drive_file_id, temp_path, mime_type):
    """Splits the file at `temp_path` into fixed-size blocks, plans their
    distribution across the user's connected accounts, and uploads every
    block (and its redundancy replicas) concurrently. Runs in the Celery
    worker so the original request can return immediately -- the frontend
    polls FileUploadStatusView for progress."""
    drive_file = DriveFile.objects.select_related("user").get(id=drive_file_id)
    try:
        drive_file.checksum = _sha256_of_file(temp_path)
        num_chunks = max(1, math.ceil(drive_file.size / drive_file.chunk_size))
        replicas = drive_file.replica_count

        plan = allocator.plan_allocation(drive_file.user, num_chunks, drive_file.chunk_size, replicas)

        chunk_rows = []
        for index in range(num_chunks):
            length = _chunk_len(drive_file.size, drive_file.chunk_size, index)
            for replica, account in enumerate(plan[index]):
                chunk_rows.append(
                    FileChunk.objects.create(
                        file=drive_file, index=index, replica_number=replica,
                        account=account, size=length,
                    )
                )

        with ThreadPoolExecutor(max_workers=settings.CHUNK_UPLOAD_CONCURRENCY) as pool:
            futures = [pool.submit(_upload_one_chunk, row.id, temp_path, mime_type) for row in chunk_rows]
            for future in as_completed(futures):
                future.result()  # exceptions are already handled/logged inside _upload_one_chunk

        drive_file.status = health.recompute_status(drive_file)
    except Exception:
        # Anything unexpected here (allocation failure, disk error, etc.)
        # must not leave the file stuck in "uploading" forever.
        drive_file.status = DriveFile.STATUS_FAILED
    finally:
        drive_file.save(update_fields=["checksum", "status", "updated_at"])
        try:
            os.remove(temp_path)
        except OSError:
            pass

    from notifications.models import Notification
    from notifications.service import notify

    if drive_file.status == DriveFile.STATUS_AVAILABLE:
        notify(
            drive_file.user, category=Notification.CATEGORY_UPLOAD, level=Notification.LEVEL_INFO,
            title=f'"{drive_file.name}" finished uploading', link="/files", send_email=False,
        )
        # Best-effort, non-billable auto-categorization -- the user didn't
        # ask for this, so it must never eat their AI query quota or block
        # the upload if it fails (see ai.tasks.categorize_files_task).
        from ai.tasks import categorize_files_task

        categorize_files_task.delay([drive_file.id], billable=False)
    else:
        # Covers both FAILED and PARTIALLY_AVAILABLE -- either way the
        # file isn't fully usable and is worth an email, not just an
        # in-app ping.
        notify(
            drive_file.user, category=Notification.CATEGORY_UPLOAD, level=Notification.LEVEL_CRITICAL,
            title=f'"{drive_file.name}" upload had a problem',
            body=f"Status: {drive_file.get_status_display()}. Some blocks could not be uploaded.",
            link="/files", send_email=True,
        )
