"""Bounded Sarvam tool-calling executor. See build brief section 9.

Multiple tool_calls in one assistant turn are dispatched sequentially, never
concurrently, so state-changing calls can't race each other.
"""

import json
import logging

from django.conf import settings

from .prompts import SYSTEM_PROMPT
from .sarvam_client import chat_completion
from .tool_registry import dispatch
from .tool_schemas import TOOL_SCHEMAS

logger = logging.getLogger("paytrail.agent")


def _backfill_case_link(case_id: str, request_ids: list[str]) -> None:
    """Retroactively attach this turn's pre-case tool calls to the case they informed.

    investigate_payment_case, search_support_knowledge and inspect_device
    have no case_id argument — a case doesn't exist yet when they run, that's
    correct. But it means tool_registry.dispatch's case-FK linking (by
    arguments["case_id"]) always leaves them unlinked, so a case's dashboard
    timeline silently started at the first post-creation action, making a
    thoroughly-investigated case look like evidence was skipped. Everything
    dispatched earlier in this same turn, still unlinked, belongs to the case
    this turn just created.
    """
    from agent.models import ToolExecution
    from support.models import SupportCase

    try:
        case = SupportCase.objects.get(case_id=case_id)
    except SupportCase.DoesNotExist:
        return
    ToolExecution.objects.filter(request_id__in=request_ids, case__isnull=True).update(case=case)


def _clean(message: dict) -> dict:
    """Drop null-valued keys before echoing a message back to the provider.

    Sarvam returns `tool_calls: null` on plain replies and `content: null` on
    tool-call messages; forwarding those explicit nulls back is rejected by
    OpenAI-compatible endpoints, so they are stripped rather than sent.
    """
    return {key: value for key, value in message.items() if value is not None}


def stream_turn(conversation: list[dict], merchant_message: str):
    """Generator core of the agent loop — yields one event per tool call as it
    completes, then one final event, so a caller (the streaming API view) can
    forward progress to the merchant live instead of after the whole bounded
    loop finishes. run_turn() below is a non-streaming wrapper around this for
    callers that just want the end result (scripts/cli_chat.py).

    Yields:
      {"type": "tool_result", "tool_name": str, "arguments": dict, "result": envelope}
      {"type": "final", "final_message": str, "messages": full transcript incl. system prompt}
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *(_clean(m) for m in conversation),
        {"role": "user", "content": merchant_message},
    ]
    tool_call_count = 0
    turn_request_ids: list[str] = []
    logger.info("TURN START merchant_message=%r (history=%d msgs)", merchant_message, len(conversation))

    for round_number in range(1, settings.AGENT_MAX_TOOL_ROUNDS + 1):
        response = chat_completion(messages, tools=TOOL_SCHEMAS, tool_choice="auto")
        choice = response["choices"][0]
        message = choice["message"]
        messages.append(message)

        tool_calls = message.get("tool_calls") or []
        logger.info(
            "round %d/%d finish_reason=%s tool_calls=%s",
            round_number,
            settings.AGENT_MAX_TOOL_ROUNDS,
            choice.get("finish_reason"),
            [c["function"]["name"] for c in tool_calls] or "none",
        )

        if not tool_calls:
            final = message.get("content", "")
            logger.info("TURN END after %d round(s), %d tool call(s)", round_number, tool_call_count)
            yield {"type": "final", "final_message": final, "messages": messages}
            return

        for call in tool_calls:
            name = call["function"]["name"]
            raw_arguments = call["function"].get("arguments") or "{}"
            try:
                arguments = json.loads(raw_arguments)
            except json.JSONDecodeError:
                logger.warning("model sent unparseable arguments for %s: %r", name, raw_arguments)
                arguments = {}

            envelope = dispatch(name, arguments)
            turn_request_ids.append(envelope["meta"]["request_id"])
            tool_call_count += 1
            messages.append(
                {"role": "tool", "tool_call_id": call["id"], "content": json.dumps(envelope)}
            )

            if envelope["ok"] and name == "manage_support_case" and envelope["data"].get("operation") == "CREATE":
                _backfill_case_link(envelope["data"]["case_id"], turn_request_ids)

            yield {"type": "tool_result", "tool_name": name, "arguments": arguments, "result": envelope}

    logger.warning(
        "TURN HIT ROUND LIMIT (%d) with %d tool call(s) — handing off",
        settings.AGENT_MAX_TOOL_ROUNDS,
        tool_call_count,
    )
    # ponytail: loop-limit fallback is a static message, not an auto-escalation
    # case. Good enough for the demo; wire manage_support_case(ESCALATE) here
    # if a scripted case ever actually hits 8 rounds.
    yield {
        "type": "final",
        "final_message": (
            "I've reached my investigation limit for this turn. Handing this off "
            "to a human teammate with the evidence gathered so far."
        ),
        "messages": messages,
    }


def run_turn(conversation: list[dict], merchant_message: str) -> dict:
    """Non-streaming wrapper around stream_turn(). Returns
    {"final_message": str, "messages": full updated transcript, "tool_trace": [...]}.
    """
    tool_trace: list[dict] = []
    final_event: dict = {}
    for event in stream_turn(conversation, merchant_message):
        if event["type"] == "tool_result":
            tool_trace.append(
                {"tool_name": event["tool_name"], "arguments": event["arguments"], "result": event["result"]}
            )
        else:
            final_event = event
    return {
        "final_message": final_event["final_message"],
        "messages": final_event["messages"],
        "tool_trace": tool_trace,
    }
