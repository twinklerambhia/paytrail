#!/usr/bin/env python
"""Text-only REPL against the full agent loop — proves scenarios A/B/C end to
end before any UI exists. Needs migrate + seed_demo_data run first.

Run: uv run python scripts/cli_chat.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from agent.agent_loop import run_turn  # noqa: E402


def main() -> None:
    conversation: list[dict] = []
    print("PayTrail CLI — type as the merchant. Ctrl+C to quit.\n")
    while True:
        try:
            message = input("merchant> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not message:
            continue

        result = run_turn(conversation, message)
        conversation = result["messages"][1:]

        for step in result["tool_trace"]:
            status = "OK" if step["result"]["ok"] else f"ERROR:{step['result']['error']['code']}"
            print(f"  [tool] {step['tool_name']} -> {status}")
        print(f"paytrail> {result['final_message']}\n")


if __name__ == "__main__":
    main()
