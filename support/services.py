import uuid

from agent.errors import (
    InvalidStateTransitionError,
    RecordNotFoundError,
    ToolInputError,
)
from merchants.models import Merchant

from .models import SupportCase, SupportCaseNote, VerificationRecord

Status = SupportCase.Status

# Mirrors knowledge_base/escalation_policy.md's "Team routing" table. The
# model is supposed to pass assigned_team on escalation but has been
# observed (confirmed via live tool-call logs) reliably forgetting it while
# still setting target_status=ESCALATED. Relying on an LLM to remember a
# field every time is fragile; the backend is the authority here, so a case
# transitioning to ESCALATED with no team gets routed deterministically.
DEFAULT_ESCALATION_TEAM: dict[str, str] = {
    SupportCase.IssueType.SOUNDBOX_NO_ALERT: "DEVICE_SUPPORT",
    SupportCase.IssueType.PENDING_PAYMENT: "PAYMENTS_OPS",
    SupportCase.IssueType.PAYMENT_FAILED: "PAYMENTS_OPS",
    SupportCase.IssueType.PAYMENT_STATUS_DISPUTE: "PAYMENTS_OPS",
    SupportCase.IssueType.SETTLEMENT_QUERY: "PAYMENTS_OPS",
    SupportCase.IssueType.UNKNOWN: "GENERAL_SUPPORT",
}

# Terminal states have no outgoing transitions. RESOLVED is only reachable
# when get_latest_verification() shows VERIFIED + issue_resolved=True — that
# check happens in transition_status(), not here.
VALID_TRANSITIONS: dict[str, set[str]] = {
    Status.OPEN: {Status.IN_PROGRESS, Status.AWAITING_APPROVAL, Status.ESCALATED, Status.RESOLVED, Status.CLOSED},
    Status.IN_PROGRESS: {Status.AWAITING_APPROVAL, Status.ESCALATED, Status.RESOLVED, Status.CLOSED},
    Status.AWAITING_APPROVAL: {Status.IN_PROGRESS, Status.ESCALATED, Status.CLOSED},
    Status.ESCALATED: {Status.IN_PROGRESS, Status.RESOLVED, Status.CLOSED},
    Status.RESOLVED: {Status.CLOSED},
    Status.CLOSED: set(),
}


def get_case(case_id: str) -> SupportCase:
    try:
        return SupportCase.objects.select_related("merchant", "transaction").get(case_id=case_id)
    except SupportCase.DoesNotExist:
        raise RecordNotFoundError(f"No support case found for case_id={case_id!r}.")


def open_cases_for_merchant(merchant: Merchant) -> list[dict]:
    qs = merchant.cases.exclude(status__in=[Status.RESOLVED, Status.CLOSED])
    return [case_to_dict(c) for c in qs]


def get_latest_verification(case: SupportCase) -> VerificationRecord | None:
    return case.verifications.first()  # Meta.ordering = ["-created_at"]


def record_verification(case: SupportCase, **fields) -> VerificationRecord:
    return VerificationRecord.objects.create(case=case, **fields)


def case_to_dict(case: SupportCase) -> dict:
    return {
        "case_id": case.case_id,
        "merchant_id": case.merchant.merchant_id,
        "transaction_id": case.transaction.transaction_id if case.transaction else None,
        "issue_type": case.issue_type,
        "status": case.status,
        "priority": case.priority,
        "assigned_team": case.assigned_team,
        "summary": case.summary,
        "created_at": case.created_at.isoformat(),
        "updated_at": case.updated_at.isoformat(),
        "evidence_refs": case.evidence_refs,
    }


def _next_case_id() -> str:
    return f"CASE{uuid.uuid4().hex[:6].upper()}"


def manage_case(
    operation: str,
    idempotency_key: str,
    merchant_id: str | None = None,
    transaction=None,
    case_id: str | None = None,
    issue_type: str | None = None,
    summary: str | None = None,
    details: str | None = None,
    priority: str | None = None,
    target_status: str | None = None,
    assigned_team: str | None = None,
    note: str | None = None,
    evidence_refs: list[str] | None = None,
) -> dict:
    if operation == "CREATE":
        existing = SupportCase.objects.filter(create_idempotency_key=idempotency_key).first()
        if existing is not None:
            return case_to_dict(existing)
        if not merchant_id or not issue_type:
            raise ToolInputError("CREATE requires merchant_id and issue_type.")
        try:
            merchant = Merchant.objects.get(merchant_id=merchant_id)
        except Merchant.DoesNotExist:
            raise RecordNotFoundError(f"No merchant found for merchant_id={merchant_id!r}.")
        case = SupportCase.objects.create(
            case_id=_next_case_id(),
            merchant=merchant,
            transaction=transaction,
            issue_type=issue_type,
            priority=priority or SupportCase.Priority.MEDIUM,
            summary=summary,
            details=details,
            assigned_team=assigned_team,
            evidence_refs=evidence_refs or [],
            create_idempotency_key=idempotency_key,
        )
        return case_to_dict(case)

    if not case_id:
        raise ToolInputError(f"{operation} requires case_id.")
    case = get_case(case_id)

    if operation == "GET_STATUS":
        return case_to_dict(case)

    if operation not in ("ADD_NOTE", "ASSIGN", "UPDATE"):
        raise ToolInputError(f"Unsupported operation={operation!r}.")

    # Each operation has its own required field, but all three apply the same
    # optional fields if present — the tool schema lets the model send e.g. a
    # note AND a status transition in one ADD_NOTE call (a real escalation
    # note plus target_status=ESCALATED is the obvious, expected usage), and
    # silently dropping the fields an operation doesn't "own" is what broke
    # this exact case: an escalation note landed, but the status never moved.
    if operation == "ADD_NOTE" and not note:
        raise ToolInputError("ADD_NOTE requires note.")
    if operation == "ASSIGN" and not assigned_team:
        raise ToolInputError("ASSIGN requires assigned_team.")

    if note:
        SupportCaseNote.objects.create(case=case, note=note)
    if assigned_team is not None:
        case.assigned_team = assigned_team
    if summary is not None:
        case.summary = summary
    if details is not None:
        case.details = details
    if priority is not None:
        case.priority = priority
    if evidence_refs:
        case.evidence_refs = list({*case.evidence_refs, *evidence_refs})
    if target_status:
        transition_status(case, target_status)
    case.save()
    return case_to_dict(case)


def transition_status(case: SupportCase, target_status: str) -> None:
    if target_status not in VALID_TRANSITIONS:
        raise ToolInputError(f"Unknown target_status={target_status!r}.")
    if target_status == case.status:
        return
    if target_status not in VALID_TRANSITIONS[case.status]:
        raise InvalidStateTransitionError(f"Cannot move case from {case.status} to {target_status}.")
    if target_status == Status.RESOLVED:
        latest = get_latest_verification(case)
        if latest is None or latest.status != VerificationRecord.VerificationStatus.VERIFIED or not latest.issue_resolved:
            raise InvalidStateTransitionError(
                "RESOLVED requires a VerificationRecord with status=VERIFIED and issue_resolved=True."
            )
    case.status = target_status
    if target_status == Status.ESCALATED and not case.assigned_team:
        case.assigned_team = DEFAULT_ESCALATION_TEAM.get(case.issue_type, "GENERAL_SUPPORT")
