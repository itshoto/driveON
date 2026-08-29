from concurrent.futures import ThreadPoolExecutor

from django.conf import settings

from accounts.client import get_client
from accounts.models import StorageAccount

from .models import FileChunk


def _pick_one_available_replica_per_index(drive_file):
    """{index: FileChunk} using, for each logical block, an available
    replica on a connected account -- lowest replica_number preferred so
    reconstruction is deterministic when multiple replicas are healthy."""
    chunks = (
        drive_file.chunks.select_related("account")
        .filter(status=FileChunk.STATUS_AVAILABLE, account__status=StorageAccount.STATUS_CONNECTED)
        .order_by("index", "replica_number")
    )
    selected = {}
    for chunk in chunks:
        selected.setdefault(chunk.index, chunk)
    return selected


def _download_chunk_bytes(chunk):
    return b"".join(get_client(chunk.account).download_file_stream(chunk.google_file_id))


def stream_reconstructed(drive_file, concurrency=None):
    """Generator yielding the file's bytes in order while fetching up to
    `concurrency` blocks from (potentially different) accounts at once --
    a bounded sliding window, so transfers genuinely overlap even though
    the caller receives strictly ordered output for its
    StreamingHttpResponse. Callers must check the file's health before
    calling this (see files.health) -- a block with no available replica
    is not handled here and would truncate the stream."""
    concurrency = concurrency or settings.CHUNK_DOWNLOAD_CONCURRENCY
    selected = _pick_one_available_replica_per_index(drive_file)
    ordered = [selected[i] for i in sorted(selected)]
    if not ordered:
        raise ValueError("No chunks available to reconstruct this file.")

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {i: pool.submit(_download_chunk_bytes, ordered[i]) for i in range(min(concurrency, len(ordered)))}
        for i in range(len(ordered)):
            data = futures.pop(i).result()
            next_index = i + concurrency
            if next_index < len(ordered):
                futures[next_index] = pool.submit(_download_chunk_bytes, ordered[next_index])
            yield data
