from rest_framework.response import Response
from rest_framework.views import APIView

from agent.agent_loop import run_turn
from agent.models import ToolExecution
from support.models import SupportCase
from support.services import case_to_dict, get_case

from .serializers import AgentMessageRequestSerializer


class AgentMessageView(APIView):
    """POST {message, conversation} -> runs one bounded agent turn.

    Stateless: the client (Streamlit) holds the conversation transcript and
    resends it each turn; we re-attach the system prompt internally.
    """

    def post(self, request):
        serializer = AgentMessageRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = run_turn(
            conversation=serializer.validated_data.get("conversation", []),
            merchant_message=serializer.validated_data["message"],
        )
        return Response(
            {
                "final_message": result["final_message"],
                "tool_trace": result["tool_trace"],
                "conversation": result["messages"][1:],  # drop the system prompt
            }
        )


class CaseDetailView(APIView):
    """GET case + notes + verifications + device actions + tool calls — the support/observability view."""

    def get(self, request, case_id: str):
        case = get_case(case_id)
        return Response(
            {
                "case": case_to_dict(case),
                "notes": [{"note": n.note, "created_at": n.created_at.isoformat()} for n in case.notes.all()],
                "verifications": [
                    {
                        "verification_scope": v.verification_scope,
                        "status": v.status,
                        "issue_resolved": v.issue_resolved,
                        "observed_state": v.observed_state,
                        "mismatches": v.mismatches,
                        "created_at": v.created_at.isoformat(),
                    }
                    for v in case.verifications.all()
                ],
                "device_actions": [
                    {
                        "action_id": a.action_id,
                        "action": a.action,
                        "execution_status": a.execution_status,
                        "result": a.result,
                        "executed_at": a.executed_at.isoformat(),
                    }
                    for a in case.device_actions.all()
                ],
                "tool_executions": [
                    {
                        "tool_name": t.tool_name,
                        "ok": t.ok,
                        "error_code": t.error_code,
                        "created_at": t.created_at.isoformat(),
                    }
                    for t in ToolExecution.objects.filter(case=case).order_by("created_at")
                ],
            }
        )


class CaseListView(APIView):
    """GET all cases, most recently updated first — support dashboard landing list."""

    def get(self, request):
        cases = SupportCase.objects.select_related("merchant").order_by("-updated_at")[:50]
        return Response({"cases": [case_to_dict(c) for c in cases]})
