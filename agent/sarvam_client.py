"""Isolated Sarvam Chat Completions client.

NOT YET LIVE-VERIFIED. Assumes an OpenAI-compatible /v1/chat/completions
shape per https://docs.sarvam.ai/api-reference/chat/chat-completions-v2,
with an api-subscription-key header (Sarvam's documented pattern for their
other APIs). Run scripts/test_sarvam_connection.py against a real key before
trusting this — if the endpoint path, auth header, or response shape differ,
fix only this file; nothing else in agent/ should need to change.
"""

import logging

import requests
from django.conf import settings

from .errors import DependencyUnavailableError

logger = logging.getLogger("paytrail.sarvam")

CHAT_COMPLETIONS_PATH = "/v1/chat/completions"
SPEECH_TO_TEXT_PATH = "/speech-to-text"


def chat_completion(messages: list[dict], tools: list[dict] | None = None, tool_choice: str = "auto") -> dict:
    if not settings.SARVAM_API_KEY:
        raise DependencyUnavailableError("SARVAM_API_KEY is not set.")

    payload = {"model": settings.SARVAM_MODEL_ID, "messages": messages}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice

    logger.debug(
        "POST %s model=%s messages=%d tools=%d",
        CHAT_COMPLETIONS_PATH,
        settings.SARVAM_MODEL_ID,
        len(messages),
        len(tools or []),
    )

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
        logger.error("chat_completion transport failure: %s", exc)
        raise DependencyUnavailableError(f"Sarvam request failed: {exc}")

    if response.status_code >= 400:
        logger.error("chat_completion HTTP %s body=%s", response.status_code, response.text[:1000])
        raise DependencyUnavailableError(
            f"Sarvam returned {response.status_code}: {response.text[:500]}"
        )

    payload_out = response.json()
    logger.debug("chat_completion HTTP 200 raw=%s", str(payload_out)[:1500])
    return payload_out


def speech_to_text(audio_bytes: bytes, filename: str = "audio.webm", language_code: str = "unknown") -> str:
    """Transcribe merchant audio via Sarvam STT. Returns the transcript text.

    Same caveat as chat_completion: endpoint/field names are not live-verified.
    language_code "unknown" asks Sarvam to auto-detect, which is what we want
    for code-mixed Hindi/English merchant speech.
    """
    if not settings.SARVAM_API_KEY:
        raise DependencyUnavailableError("SARVAM_API_KEY is not set.")

    try:
        response = requests.post(
            f"{settings.SARVAM_BASE_URL.rstrip('/')}{SPEECH_TO_TEXT_PATH}",
            headers={"api-subscription-key": settings.SARVAM_API_KEY},
            files={"file": (filename, audio_bytes, "audio/webm")},
            data={"model": settings.SARVAM_STT_MODEL_ID, "language_code": language_code},
            timeout=60,
        )
    except requests.RequestException as exc:
        logger.error("speech_to_text transport failure: %s", exc)
        raise DependencyUnavailableError(f"Sarvam speech-to-text request failed: {exc}")

    if response.status_code >= 400:
        logger.error("speech_to_text HTTP %s body=%s", response.status_code, response.text[:1000])
        raise DependencyUnavailableError(
            f"Sarvam speech-to-text returned {response.status_code}: {response.text[:500]}"
        )

    payload = response.json()
    logger.debug("speech_to_text HTTP 200 raw=%s", str(payload)[:800])
    transcript = payload.get("transcript") or payload.get("text") or ""
    if not transcript:
        logger.error("speech_to_text returned no transcript field; payload=%s", str(payload)[:800])
        raise DependencyUnavailableError("Sarvam speech-to-text returned no transcript.")
    logger.info("speech_to_text transcript=%r", transcript)
    return transcript
