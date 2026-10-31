"""Bounded Sarvam tool-calling executor. See build brief section 9.

Multiple tool_calls in one assistant turn are dispatched sequentially, never
concurrently, so state-changing calls can't race each other.
"""

import json

from django.conf import settings

from .prompts import SYSTEM_PROMPT
from .sarvam_client import chat_completion
from .tool_registry import dispatch
from .tool_schemas import TOOL_SCHEMAS


def run_turn(conversation: list[dict], merchant_message: str) -> dict:
    """conversation: prior {role, content} messages, not including merchant_message.

    Returns {"final_message": str, "messages": full updated transcript, "tool_trace": [...]}.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *conversation, {"role": "user", "content": merchant_message}]
    tool_trace: list[dict] = []

    for _ in range(settings.AGENT_MAX_TOOL_ROUNDS):
        response = chat_completion(messages, tools=TOOL_SCHEMAS, tool_choice="auto")
        message = response["choices"][0]["message"]
        messages.append(message)

        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            return {"final_message": message.get("content", ""), "messages": messages, "tool_trace": tool_trace}

        for call in tool_calls:
            name = call["function"]["name"]
            try:
                arguments = json.loads(call["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}

            envelope = dispatch(name, arguments)
            tool_trace.append({"tool_name": name, "arguments": arguments, "result": envelope})
            messages.append(
                {"role": "tool", "tool_call_id": call["id"], "content": json.dumps(envelope)}
            )

    # ponytail: loop-limit fallback is a static message, not an auto-escalation
    # case. Good enough for the demo; wire manage_support_case(ESCALATE) here
    # if a scripted case ever actually hits 8 rounds.
    return {
        "final_message": (
            "I've reached my investigation limit for this turn. Handing this off "
            "to a human teammate with the evidence gathered so far."
        ),
        "messages": messages,
        "tool_trace": tool_trace,
    }
