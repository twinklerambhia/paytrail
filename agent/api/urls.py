from django.urls import path

from .views import AgentMessageView, CaseDetailView, CaseListView

urlpatterns = [
    path("message/", AgentMessageView.as_view(), name="agent-message"),
    path("cases/", CaseListView.as_view(), name="case-list"),
    path("cases/<str:case_id>/", CaseDetailView.as_view(), name="case-detail"),
]
