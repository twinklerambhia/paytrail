#!/usr/bin/env python
"""One-shot Sarvam connectivity check.

Confirms SARVAM_API_KEY/SARVAM_MODEL_ID actually work, and whether the
tool-calling round trip matches the assumptions baked into
agent/sarvam_client.py (endpoint path, auth header, response shape). Run
this before trusting anything else in agent/ — if it fails, the fix belongs
in sarvam_client.py only.

Run: uv run python scripts/test_sarvam_connection.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from agent.sarvam_client import chat_completion  # noqa: E402


def main() -> None:
    print("1) Plain chat completion (no tools)...")
    response = chat_completion([{"role": "user", "content": "Reply with exactly: PAYTRAIL_OK"}])
    print(response)

    print("\n2) Tool-calling round trip...")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "ping",
                "description": "Call this to confirm tool calling works.",
                "parameters": {
                    "type": "object",
                    "properties": {"note": {"type": ["string", "null"]}},
                    "required": [],
                },
            },
        }
    ]
    response = chat_completion(
        [{"role": "user", "content": "Call the ping tool now with note set to 'hello'."}],
        tools=tools,
    )
    print(response)
    print(
        "\nCheck above: does response['choices'][0]['message'] contain 'tool_calls' "
        "with function.name == 'ping' and function.arguments as a JSON string? "
        "If the shape differs, fix agent/sarvam_client.py and agent/agent_loop.py only."
    )


if __name__ == "__main__":
    main()
