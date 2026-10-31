from agent.errors import ToolInputError
from devices.services import device_summary
from payments.services import events_for_transaction, resolve_transaction, transaction_to_dict
from support.models import SupportCase
from support.services import open_cases_for_merchant

ISSUE_TYPES = {choice for choice, _ in SupportCase.IssueType.choices}


def investigate_payment_case(
    transaction_id: str | None = None,
    merchant_id: str | None = None,
    issue_type: str = "unknown",
    include_device_context: bool = True,
    include_open_cases: bool = True,
) -> dict:
    """Read-only, correlated evidence gathering. See PayTrail_Agent_Tool_Specification.md section 3."""
    if issue_type not in ISSUE_TYPES:
        raise ToolInputError(f"Unsupported issue_type={issue_type!r}.")

    transaction = resolve_transaction(transaction_id, merchant_id)
    merchant = transaction.merchant

    device_summary_data = None
    if include_device_context:
        device = merchant.devices.first()
        if device is not None:
            device_summary_data = device_summary(device)

    related_cases = open_cases_for_merchant(merchant) if include_open_cases else []

    return {
        "transaction": transaction_to_dict(transaction),
        "payment_events": events_for_transaction(transaction),
        "device_summary": device_summary_data,
        "related_open_cases": related_cases,
        "evidence_complete": True,
        "warnings": [],
    }
