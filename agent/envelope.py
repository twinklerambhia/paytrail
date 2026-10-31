"""Common ok/data/error/meta result envelope shared by every agent tool."""

import uuid
from datetime import datetime, timezone

from .errors import ToolError


def new_request_id() -> str:
    return f"REQ{uuid.uuid4().hex[:10].upper()}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_success(data: dict, tool_name: str, request_id: str) -> dict:
    return {
        "ok": True,
        "data": data,
        "error": None,
        "meta": {
            "tool_name": tool_name,
            "request_id": request_id,
            "observed_at": now_iso(),
        },
    }


def build_error(exc: Exception, tool_name: str, request_id: str) -> dict:
    if isinstance(exc, ToolError):
        code, message, retryable = exc.code, str(exc) or exc.__class__.__name__, exc.retryable
    else:
        # Never leak raw exception/traceback detail to the model.
        code, message, retryable = "INTERNAL_ERROR", "An internal error occurred.", False
    return {
        "ok": False,
        "data": None,
        "error": {"code": code, "message": message, "retryable": retryable},
        "meta": {
            "tool_name": tool_name,
            "request_id": request_id,
            "observed_at": now_iso(),
        },
    }
