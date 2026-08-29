from django.urls import path

from .views import (
    AIQuotaView,
    CategorizeView,
    ConversationDetailView,
    ConversationListView,
    ConversationMessageView,
    FileSummaryView,
    SearchView,
)

urlpatterns = [
    path("quota", AIQuotaView.as_view(), name="ai-quota"),
    path("files/<int:file_id>/summary", FileSummaryView.as_view(), name="ai-file-summary"),
    path("conversations", ConversationListView.as_view(), name="ai-conversations"),
    path("conversations/<int:conversation_id>", ConversationDetailView.as_view(), name="ai-conversation-detail"),
    path(
        "conversations/<int:conversation_id>/messages",
        ConversationMessageView.as_view(),
        name="ai-conversation-messages",
    ),
    path("search", SearchView.as_view(), name="ai-search"),
    path("categorize", CategorizeView.as_view(), name="ai-categorize"),
]
