import base64
from io import BytesIO

from django.conf import settings
from django.utils import timezone

from files import health, reconstruction
from files.models import DriveFile

from . import prompts
from .client import get_client
from .models import AIMessage, AISummary
from .quota import record_usage


class AIDocumentError(Exception):
    """A file can't be handed to Claude at all (wrong type, too big, or
    currently unreachable) -- distinct from a Claude API error, and never
    counted against quota since no API call was made."""


def check_document_eligible(drive_file):
    if drive_file.mime_type != "application/pdf":
        raise AIDocumentError("Only PDF files can be used with AI features right now.")
    max_bytes = settings.AI_MAX_DOCUMENT_SIZE_MB * 1024 * 1024
    if drive_file.size > max_bytes:
        raise AIDocumentError(f"This file is larger than the {settings.AI_MAX_DOCUMENT_SIZE_MB}MB AI limit.")
    if health.compute_health(drive_file).status == health.STATUS_UNAVAILABLE:
        raise AIDocumentError(f"'{drive_file.name}' isn't fully available right now.")


def _read_file_bytes(drive_file):
    """Only call after check_document_eligible -- reconstruction is a
    live parallel fetch against Google Drive/OneDrive and shouldn't run
    just to discover Claude will reject an oversized/wrong-type result."""
    return b"".join(reconstruction.stream_reconstructed(drive_file))


def summarize_file(drive_file):
    """Synchronous -- called from the Celery task, not directly from a
    view (see ai.tasks.generate_summary_task)."""
    check_document_eligible(drive_file)
    data = _read_file_bytes(drive_file)
    b64 = base64.standard_b64encode(data).decode("ascii")

    response = get_client().messages.parse(
        model=settings.AI_MODEL,
        max_tokens=16000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {"type": "base64", "media_type": "application/pdf", "data": b64},
                    },
                    {"type": "text", "text": prompts.SUMMARY_PROMPT},
                ],
            }
        ],
        output_format=prompts.SummarySchema,
    )
    parsed = response.parsed_output

    summary, _ = AISummary.objects.update_or_create(
        drive_file=drive_file,
        defaults={"summary": parsed.model_dump(), "model": settings.AI_MODEL},
    )
    record_usage(
        drive_file.user,
        "summarize",
        drive_file=drive_file,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
    return summary


def _ensure_conversation_file_uploaded(conv_file):
    """Lazy, on first use -- this is why the first message in a
    conversation is slower than later ones (reconstruction + upload
    happen here), which is an acceptable trade for not needing a separate
    async "preparing conversation" step (see ai.views)."""
    if conv_file.claude_file_id:
        return conv_file.claude_file_id

    drive_file = conv_file.drive_file
    check_document_eligible(drive_file)
    data = _read_file_bytes(drive_file)

    uploaded = get_client().beta.files.upload(file=(drive_file.name, BytesIO(data), "application/pdf"))
    conv_file.claude_file_id = uploaded.id
    conv_file.save(update_fields=["claude_file_id"])
    return uploaded.id


def send_chat_message(conversation, content):
    """The Messages API is stateless, so every call must resend full
    history -- including the document blocks from the very first turn.
    Storing only plain text in AIMessage and reconstructing the first
    turn's document blocks fresh on every call (rather than trying to
    persist/replay the original content array) keeps AIMessage simple
    while still giving Claude the documents on every turn; the blocks are
    byte-identical each time, so the cache_control breakpoint right after
    them lets Anthropic's prompt cache serve them from turn 2 onward."""
    conv_files = list(conversation.conversation_files.select_related("drive_file").order_by("drive_file_id"))
    if not conv_files:
        raise AIDocumentError("This conversation has no files attached.")

    file_ids = [_ensure_conversation_file_uploaded(cf) for cf in conv_files]
    doc_blocks = [{"type": "document", "source": {"type": "file", "file_id": fid}} for fid in file_ids]

    prior = list(conversation.messages.all())
    messages = []
    if not prior:
        messages.append(
            {"role": "user", "content": [*doc_blocks, {"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}]}
        )
    else:
        first_turn_text = prior[0].content
        messages.append(
            {
                "role": "user",
                "content": [*doc_blocks, {"type": "text", "text": first_turn_text, "cache_control": {"type": "ephemeral"}}],
            }
        )
        for message in prior[1:]:
            messages.append({"role": message.role, "content": message.content})
        messages.append({"role": "user", "content": content})

    response = get_client().beta.messages.create(
        model=settings.AI_MODEL,
        max_tokens=16000,
        betas=["files-api-2025-04-14"],
        cache_control={"type": "ephemeral"},
        system=[{"type": "text", "text": prompts.CHAT_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=messages,
    )
    reply_text = next((block.text for block in response.content if block.type == "text"), "")

    AIMessage.objects.create(conversation=conversation, role=AIMessage.ROLE_USER, content=content)
    AIMessage.objects.create(conversation=conversation, role=AIMessage.ROLE_ASSISTANT, content=reply_text)
    conversation.save(update_fields=["updated_at"])

    record_usage(
        conversation.user,
        "chat",
        conversation=conversation,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
    return reply_text


def delete_conversation(conversation):
    """Uploaded Claude files persist until deleted against a 100GB
    org-wide cap -- this cleanup is required, not optional tidiness."""
    client = get_client()
    for conv_file in conversation.conversation_files.exclude(claude_file_id=""):
        try:
            client.beta.files.delete(conv_file.claude_file_id)
        except Exception:
            pass
    conversation.delete()


def _file_listing_line(drive_file, include_summary=True):
    parts = [
        f'id={drive_file.id} name="{drive_file.name}" type={drive_file.mime_type} '
        f"size={drive_file.size} modified={drive_file.updated_at.date()} "
        f"category={drive_file.category or 'uncategorized'}"
    ]
    if include_summary and hasattr(drive_file, "ai_summary"):
        keywords = drive_file.ai_summary.summary.get("keywords") or []
        if keywords:
            parts.append(f"keywords={keywords}")
    return " ".join(parts)


def search_files(user, query, limit=400):
    qs = DriveFile.objects.filter(user=user, deleted_at__isnull=True).select_related("ai_summary")
    total_count = qs.count()
    files = list(qs.order_by("-created_at")[:limit])

    listing = "\n".join(_file_listing_line(f) for f in files) or "(no files)"

    response = get_client().messages.parse(
        model=settings.AI_MODEL,
        max_tokens=16000,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Files:\n{listing}", "cache_control": {"type": "ephemeral"}},
                    {"type": "text", "text": prompts.SEARCH_INSTRUCTIONS_TEMPLATE.format(query=query)},
                ],
            }
        ],
        output_format=prompts.SearchResults,
    )
    parsed = response.parsed_output

    record_usage(
        user, "search", input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens
    )

    by_id = {f.id: f for f in files}
    results = []
    for item in parsed.results:
        if item.relevance not in ("high", "medium"):
            continue
        matched = by_id.get(item.file_id)
        if matched is None:
            continue
        results.append({"file_id": matched.id, "name": matched.name, "relevance": item.relevance, "reason": item.reason})

    return {
        "query": query,
        "results": results,
        "considered_count": len(files),
        "truncated": total_count > limit,
    }


def categorize_files(files, *, billable=True):
    """files: a list of DriveFile, all belonging to the same user -- one
    call, JSON array in/out, not one call per file (keeps quota cost and
    latency down; callers batch into settings.AI_CATEGORIZE_BATCH_SIZE
    chunks before calling this)."""
    files = list(files)
    if not files:
        return

    listing = "\n".join(_file_listing_line(f, include_summary=False) for f in files)

    response = get_client().messages.parse(
        model=settings.AI_MODEL,
        max_tokens=16000,
        messages=[{"role": "user", "content": prompts.CATEGORIZE_PROMPT_TEMPLATE.format(listing=listing)}],
        output_format=prompts.CategorizationBatch,
    )
    parsed = response.parsed_output

    valid_categories = dict(DriveFile.CATEGORY_CHOICES)
    by_id = {f.id: f for f in files}
    now = timezone.now()
    for item in parsed.categories:
        drive_file = by_id.get(item.file_id)
        if drive_file is None or item.category not in valid_categories:
            continue
        drive_file.category = item.category
        drive_file.categorized_at = now
        drive_file.save(update_fields=["category", "categorized_at"])

    record_usage(
        files[0].user,
        "categorize",
        billable=billable,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
