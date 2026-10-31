import json
import logging

from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from agent.agent_loop import run_turn, stream_turn
from agent.errors import ToolError
from agent.models import ToolExecution
from agent.sarvam_client import speech_to_text
from support.models import SupportCase
from support.services import case_to_dict, get_case

from .serializers import AgentMessageRequestSerializer

logger = logging.getLogger("paytrail.api")


class AgentMessageView(APIView):
    """POST {message, conversation} -> runs one bounded agent turn.

    Stateless: the client (Streamlit) holds the conversation transcript and
    resends it each turn; we re-attach the system prompt internally.
    """

    def post(self, request):
        serializer = AgentMessageRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message = serializer.validated_data["message"]
        logger.info("POST /message/ message=%r", message)
        try:
            result = run_turn(
                conversation=serializer.validated_data.get("conversation", []),
                merchant_message=message,
            )
        except ToolError as exc:
            # Sarvam unreachable / misconfigured — return a clean 502 rather
            # than a 500 HTML page the frontend can't parse.
            logger.error("agent turn failed: %s", exc)
            return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(
            {
                "final_message": result["final_message"],
                "tool_trace": result["tool_trace"],
                "conversation": result["messages"][1:],  # drop the system prompt
            }
        )


class AgentMessageStreamView(APIView):
    """POST {message, conversation} -> Server-Sent Events, one event per tool
    call as it completes, then a final event.

    The non-streaming /message/ above still exists (unused by the web client
    now, kept for anything scripted against it) — this is what the merchant
    chat UI actually calls, so the investigation timeline appears live
    instead of appearing all at once after the whole turn finishes.

    Event shapes (each one line, "data: <json>\\n\\n"):
      {"type": "tool_result", "tool_name", "arguments", "result"}
      {"type": "final", "final_message", "conversation"}
      {"type": "error", "error"}
    """

    def post(self, request):
        serializer = AgentMessageRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = serializer.validated_data["message"]
        conversation = serializer.validated_data.get("conversation", [])
        logger.info("POST /message/stream/ message=%r", message)

        def event_stream():
            try:
                for event in stream_turn(conversation, message):
                    if event["type"] == "final":
                        event = {
                            "type": "final",
                            "final_message": event["final_message"],
                            "conversation": event["messages"][1:],  # drop the system prompt
                        }
                    yield f"data: {json.dumps(event)}\n\n"
            except ToolError as exc:
                logger.error("agent turn failed: %s", exc)
                yield f"data: {json.dumps({'type': 'error', 'error': str(exc)})}\n\n"

        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


class TranscribeView(APIView):
    """POST an audio file -> Sarvam speech-to-text -> {"transcript": "..."}.

    Transcription only. The caller then sends the transcript to /message/ like
    any typed message, so speech and text converge on the same agent loop.
    """

    parser_classes = [MultiPartParser]
    MAX_AUDIO_BYTES = 10 * 1024 * 1024

    def post(self, request):
        audio = request.FILES.get("audio")
        if audio is None:
            return Response({"error": "No audio file supplied."}, status=status.HTTP_400_BAD_REQUEST)
        if audio.size > self.MAX_AUDIO_BYTES:
            return Response({"error": "Audio file too large."}, status=status.HTTP_400_BAD_REQUEST)

        logger.info("POST /transcribe/ filename=%s bytes=%d", audio.name, audio.size)
        try:
            transcript = speech_to_text(audio.read(), filename=audio.name or "audio.webm")
        except ToolError as exc:
            logger.error("transcription failed: %s", exc)
            return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({"transcript": transcript})


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
                        "result": t.result,
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
