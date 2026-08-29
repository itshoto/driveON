from django.conf import settings
from django.db import models


class AIUsageLog(models.Model):
    """One row per billable-eligible Claude call, used purely to enforce
    Plan.ai_queries_per_month (see ai.quota). Counted per API call, not per
    file -- batching 500 files into 10 categorize calls costs 10 units."""

    FEATURE_SUMMARIZE = "summarize"
    FEATURE_CHAT = "chat"
    FEATURE_SEARCH = "search"
    FEATURE_CATEGORIZE = "categorize"
    FEATURE_CHOICES = [
        (FEATURE_SUMMARIZE, "Summarize"),
        (FEATURE_CHAT, "Chat"),
        (FEATURE_SEARCH, "Search"),
        (FEATURE_CATEGORIZE, "Categorize"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_usage_logs")
    feature = models.CharField(max_length=20, choices=FEATURE_CHOICES)
    drive_file = models.ForeignKey("files.DriveFile", null=True, blank=True, on_delete=models.SET_NULL)
    conversation = models.ForeignKey("AIConversation", null=True, blank=True, on_delete=models.SET_NULL)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    # System-triggered auto-categorization logs billable=False -- the user
    # didn't ask for it, so it shouldn't eat their monthly cap the way an
    # explicit chat/summarize/search/recategorize call does.
    billable = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "billable", "created_at"])]


class AISummary(models.Model):
    drive_file = models.OneToOneField("files.DriveFile", on_delete=models.CASCADE, related_name="ai_summary")
    # {key_findings: [...], methodology: "", dataset: "", limitations: [...], keywords: [...]}
    summary = models.JSONField()
    model = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)


class AIConversation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_conversations")
    title = models.CharField(max_length=255, blank=True)
    files = models.ManyToManyField("files.DriveFile", through="AIConversationFile", related_name="ai_conversations")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class AIConversationFile(models.Model):
    """Not a bare join row -- caches the Claude Files-API id for this PDF
    so only the FIRST message in a conversation pays for reconstruction +
    upload; every later turn just references claude_file_id."""

    conversation = models.ForeignKey(AIConversation, on_delete=models.CASCADE, related_name="conversation_files")
    drive_file = models.ForeignKey("files.DriveFile", on_delete=models.CASCADE)
    claude_file_id = models.CharField(max_length=100, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["conversation", "drive_file"], name="uniq_conv_file"),
        ]


class AIMessage(models.Model):
    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"

    conversation = models.ForeignKey(AIConversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=[(ROLE_USER, "User"), (ROLE_ASSISTANT, "Assistant")])
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
