from django.urls import path

from .views import (
    AgentMessageStreamView,
    AgentMessageView,
    CaseDetailView,
    CaseListView,
    TranscribeView,
)

urlpatterns = [
    path("message/", AgentMessageView.as_view(), name="agent-message"),
    path("message/stream/", AgentMessageStreamView.as_view(), name="agent-message-stream"),
    path("transcribe/", TranscribeView.as_view(), name="agent-transcribe"),
    path("cases/", CaseListView.as_view(), name="case-list"),
    path("cases/<str:case_id>/", CaseDetailView.as_view(), name="case-detail"),
]
