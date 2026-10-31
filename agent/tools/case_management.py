from payments.services import resolve_transaction
from support.services import manage_case


def manage_support_case(
    operation: str,
    idempotency_key: str,
    merchant_id: str | None = None,
    transaction_id: str | None = None,
    case_id: str | None = None,
    issue_type: str | None = None,
    summary: str | None = None,
    details: str | None = None,
    priority: str | None = None,
    target_status: str | None = None,
    assigned_team: str | None = None,
    note: str | None = None,
    evidence_refs: list[str] | None = None,
    reason: str | None = None,
) -> dict:
    """Create/update/assign/annotate a case. Backend enforces transitions; RESOLVED needs verification evidence."""
    transaction = resolve_transaction(transaction_id, None) if transaction_id else None
    result = manage_case(
        operation=operation,
        idempotency_key=idempotency_key,
        merchant_id=merchant_id,
        transaction=transaction,
        case_id=case_id,
        issue_type=issue_type,
        summary=summary,
        details=details,
        priority=priority,
        target_status=target_status,
        assigned_team=assigned_team,
        note=note,
        evidence_refs=evidence_refs,
    )
    result["operation"] = operation
    return result
