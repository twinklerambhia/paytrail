from django.urls import path

from .views import AgentMessageView, CaseDetailView, CaseListView, TranscribeView

urlpatterns = [
    path("message/", AgentMessageView.as_view(), name="agent-message"),
    path("transcribe/", TranscribeView.as_view(), name="agent-transcribe"),
    path("cases/", CaseListView.as_view(), name="case-list"),
    path("cases/<str:case_id>/", CaseDetailView.as_view(), name="case-detail"),
]
