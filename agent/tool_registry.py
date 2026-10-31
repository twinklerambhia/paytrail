"""Fixed name -> callable dispatch map. Never dynamically import a model-supplied name.

dispatch() is the single choke point every tool call passes through: it
builds the envelope, never lets a raw traceback reach the model, and writes
one ToolExecution audit row per call regardless of which tool ran or whether
it succeeded.
"""

import logging

from .envelope import build_error, build_success, new_request_id
from .errors import ToolInputError
from .tools.case_management import manage_support_case
from .tools.diagnostics import execute_device_action, inspect_device
from .tools.investigation import investigate_payment_case
from .tools.knowledge import search_support_knowledge
from .tools.notification import notify_merchant
from .tools.verification import verify_case_outcome

logger = logging.getLogger("paytrail.tools")

TOOL_REGISTRY = {
    "investigate_payment_case": investigate_payment_case,
    "search_support_knowledge": search_support_knowledge,
    "inspect_device": inspect_device,
    "execute_device_action": execute_device_action,
    "manage_support_case": manage_support_case,
    "verify_case_outcome": verify_case_outcome,
    "notify_merchant": notify_merchant,
}


def _resolve_case_pk(case_id: str | None):
    if not case_id:
        return None
    from support.models import SupportCase

    return SupportCase.objects.filter(case_id=case_id).values_list("pk", flat=True).first()


def dispatch(tool_name: str, arguments: dict) -> dict:
    from .models import ToolExecution  # local import: keeps this module importable pre-migration

    request_id = new_request_id()
    func = TOOL_REGISTRY.get(tool_name)
    logger.info("[%s] CALL %s args=%s", request_id, tool_name, arguments)

    if func is None:
        envelope = build_error(ToolInputError(f"Unknown tool {tool_name!r}."), tool_name, request_id)
    else:
        try:
            data = func(**arguments)
            envelope = build_success(data, tool_name, request_id)
            logger.info("[%s] OK   %s -> %s", request_id, tool_name, data)
        except TypeError as exc:
            envelope = build_error(
                ToolInputError(f"Invalid arguments for {tool_name}: {exc}"), tool_name, request_id
            )
        except Exception as exc:  # noqa: BLE001 — must never crash the agent loop
            envelope = build_error(exc, tool_name, request_id)

    ToolExecution.objects.create(
        request_id=request_id,
        tool_name=tool_name,
        case_id=_resolve_case_pk(arguments.get("case_id")),
        arguments=arguments,
        ok=envelope["ok"],
        result=envelope["data"] if envelope["ok"] else envelope["error"],
        error_code=None if envelope["ok"] else envelope["error"]["code"],
    )
    return envelope
