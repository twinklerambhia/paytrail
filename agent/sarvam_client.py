"""Isolated Sarvam Chat Completions client.

NOT YET LIVE-VERIFIED. Assumes an OpenAI-compatible /v1/chat/completions
shape per https://docs.sarvam.ai/api-reference/chat/chat-completions-v2,
with an api-subscription-key header (Sarvam's documented pattern for their
other APIs). Run scripts/test_sarvam_connection.py against a real key before
trusting this — if the endpoint path, auth header, or response shape differ,
fix only this file; nothing else in agent/ should need to change.
"""

import requests
from django.conf import settings

from .errors import DependencyUnavailableError

CHAT_COMPLETIONS_PATH = "/v1/chat/completions"


def chat_completion(messages: list[dict], tools: list[dict] | None = None, tool_choice: str = "auto") -> dict:
    if not settings.SARVAM_API_KEY:
        raise DependencyUnavailableError("SARVAM_API_KEY is not set.")

    payload = {"model": settings.SARVAM_MODEL_ID, "messages": messages}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice

    try:
        response = requests.post(
            f"{settings.SARVAM_BASE_URL.rstrip('/')}{CHAT_COMPLETIONS_PATH}",
            headers={
                "api-subscription-key": settings.SARVAM_API_KEY,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
    except requests.RequestException as exc:
        raise DependencyUnavailableError(f"Sarvam request failed: {exc}")

    if response.status_code >= 400:
        raise DependencyUnavailableError(
            f"Sarvam returned {response.status_code}: {response.text[:500]}"
        )
    return response.json()
