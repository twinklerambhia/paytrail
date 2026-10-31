"""Sarvam function/tool JSON schemas, passed via the API's `tools` parameter.

Kept separate from the system prompt per the build brief: "Tool definitions
are passed separately in the API's tools parameter — not pasted in full into
the system prompt." Names/args must stay in lockstep with tool_registry.py.
"""

ISSUE_TYPE_ENUM = [
    "pending_payment",
    "payment_failed",
    "soundbox_no_alert",
    "payment_status_dispute",
    "settlement_query",
    "unknown",
]

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "investigate_payment_case",
            "description": (
                "Gather read-only evidence relevant to a merchant payment-support complaint. "
                "Correlate the supplied transaction and/or merchant with payment status, relevant "
                "payment and notification events, linked device summary, and related open support "
                "cases. Use this before diagnosing or taking action. This tool does not change "
                "records and does not decide whether the issue is resolved."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "transaction_id": {"type": ["string", "null"], "description": "Exact transaction ID, if known."},
                    "merchant_id": {"type": ["string", "null"], "description": "Exact merchant ID, if known."},
                    "issue_type": {
                        "type": "string",
                        "enum": ISSUE_TYPE_ENUM,
                        "description": "Normalized category of the merchant's complaint.",
                    },
                    "include_device_context": {
                        "type": "boolean",
                        "description": "Whether to include a summary of the merchant's linked device. Defaults to true.",
                    },
                    "include_open_cases": {
                        "type": "boolean",
                        "description": "Whether to include related open support cases. Defaults to true.",
                    },
                },
                "required": ["issue_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_support_knowledge",
            "description": (
                "Retrieve relevant approved support SOPs, error-code explanations, troubleshooting "
                "steps, permitted-action guidance, and escalation criteria from the PayTrail "
                "knowledge base. Use when evidence needs procedural interpretation. Returned "
                "documents are guidance only; they do not grant permission to execute an action."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural-language question or issue description to search for."},
                    "issue_type": {"type": ["string", "null"], "description": "Known normalized issue category, if available."},
                    "error_codes": {"type": "array", "items": {"type": "string"}, "description": "Observed error codes from investigation results."},
                    "top_k": {"type": "integer", "minimum": 1, "maximum": 5, "description": "Maximum number of relevant chunks. Default 3."},
                    "language": {"type": "string", "enum": ["en", "hi", "mr"], "description": "Language of the query. Default en."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inspect_device",
            "description": (
                "Perform a read-only, detailed inspection of a specific Soundbox device. Use when "
                "initial investigation indicates a device issue or more detail is needed about "
                "connectivity, network, battery, notification history, or overall device health. "
                "This tool does not restart, reconnect, or otherwise modify the device."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {"type": "string", "description": "Exact Soundbox/device identifier."},
                    "inspection_type": {
                        "type": "string",
                        "enum": ["connectivity", "network", "battery", "notification_history", "full_health_check"],
                        "description": "Device subsystem or inspection scope.",
                    },
                    "transaction_id": {"type": ["string", "null"], "description": "Optional transaction ID to correlate with notification history."},
                },
                "required": ["device_id", "inspection_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_device_action",
            "description": (
                "Request an allowlisted Soundbox diagnostic or recovery action. Use only when "
                "investigation evidence supports the action. The backend independently validates "
                "device ownership, case context, prerequisites, permissions, retry limits, approval "
                "requirements, and idempotency. A completed diagnostic does not mean the merchant's "
                "issue is resolved. Never use this tool to change payment status or perform refunds."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {"type": "string", "description": "Exact target Soundbox/device ID."},
                    "action": {
                        "type": "string",
                        "enum": ["CONNECTIVITY_CHECK", "REFRESH_DEVICE_STATUS", "RETRY_NOTIFICATION", "RESTART_DEVICE"],
                        "description": "Allowlisted diagnostic or recovery action.",
                    },
                    "case_id": {"type": "string", "description": "Support case associated with the action."},
                    "reason": {"type": "string", "description": "Evidence-based reason for requesting the action."},
                    "transaction_id": {"type": ["string", "null"], "description": "Related transaction ID, if applicable."},
                    "idempotency_key": {"type": "string", "description": "Unique request key to prevent duplicate execution."},
                },
                "required": ["device_id", "action", "case_id", "reason", "idempotency_key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "manage_support_case",
            "description": (
                "Create or update a persistent merchant support case, assign it to a support team, "
                "append investigation notes, or retrieve its status. Use this to preserve case "
                "ownership and hand off gathered evidence to human support. The backend validates "
                "required fields and allowed status transitions. Do not mark a case RESOLVED unless "
                "the verification process supports resolution."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {"type": "string", "enum": ["CREATE", "UPDATE", "ASSIGN", "ADD_NOTE", "GET_STATUS"]},
                    "merchant_id": {"type": ["string", "null"]},
                    "transaction_id": {"type": ["string", "null"]},
                    "case_id": {"type": ["string", "null"]},
                    "issue_type": {"type": ["string", "null"], "enum": ISSUE_TYPE_ENUM + [None]},
                    "summary": {"type": ["string", "null"]},
                    "details": {"type": ["string", "null"]},
                    "priority": {"type": ["string", "null"], "enum": ["LOW", "MEDIUM", "HIGH", "URGENT", None]},
                    "target_status": {
                        "type": ["string", "null"],
                        "enum": ["OPEN", "IN_PROGRESS", "AWAITING_APPROVAL", "ESCALATED", "RESOLVED", "CLOSED", None],
                    },
                    "assigned_team": {"type": ["string", "null"]},
                    "note": {"type": ["string", "null"]},
                    "evidence_refs": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": ["string", "null"]},
                    "idempotency_key": {"type": "string"},
                },
                "required": ["operation", "idempotency_key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify_case_outcome",
            "description": (
                "Independently verify whether an action executed and whether the merchant's "
                "original issue is resolved. Re-read relevant current state and compare it with "
                "the expected observable outcome. Do not trust an agent claim or an action's "
                "COMPLETED status alone. If the result is VERIFIED with issue_resolved true, the "
                "backend transitions the case to RESOLVED automatically as part of this call (see "
                "case_status/case_auto_resolved in the result) — do not call manage_support_case "
                "again just to set that status. Follow up with notify_merchant using "
                "message_type=RESOLUTION and the returned verification_id."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "case_id": {"type": "string", "description": "Support case identifier."},
                    "action_id": {"type": ["string", "null"], "description": "Action identifier to verify, if applicable."},
                    "verification_scope": {
                        "type": "string",
                        "enum": ["ACTION_EXECUTION", "PAYMENT_STATUS", "DEVICE_RECOVERY", "NOTIFICATION_RECOVERY", "CASE_RESOLUTION"],
                    },
                    "expected_outcome": {"type": "string", "description": "Expected observable state, not a desired narrative."},
                    "transaction_id": {"type": ["string", "null"]},
                    "device_id": {"type": ["string", "null"]},
                },
                "required": ["case_id", "verification_scope", "expected_outcome"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "notify_merchant",
            "description": (
                "Record or send a merchant-facing progress, resolution, or escalation update for an "
                "existing support case. Use only after checking the current case state. A RESOLUTION "
                "message must be supported by a successful verification record. The prototype may "
                "record the notification in a mock communication log instead of sending a real message."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "case_id": {"type": "string"},
                    "language": {"type": "string", "enum": ["en", "hi", "mr"]},
                    "message": {"type": "string", "description": "Concise, clear merchant-facing message."},
                    "message_type": {"type": "string", "enum": ["PROGRESS", "RESOLUTION", "ESCALATION"]},
                    "verification_id": {
                        "type": ["string", "null"],
                        "description": "Required for message_type=RESOLUTION. Use the exact verification_id field from a prior verify_case_outcome result on this case where verification_status was VERIFIED and issue_resolved was true. Never guess or reuse an unrelated id such as a request_id.",
                    },
                },
                "required": ["case_id", "language", "message", "message_type"],
            },
        },
    },
]
