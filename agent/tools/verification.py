from agent.envelope import now_iso
from agent.errors import InsufficientEvidenceError, RecordNotFoundError, ToolInputError
from devices import services as device_services
from devices.models import DeviceAction
from payments.services import resolve_transaction
from support.models import VerificationRecord
from support.services import get_case, record_verification

VStatus = VerificationRecord.VerificationStatus
SCOPE_SOURCE = {
    "ACTION_EXECUTION": "device_action_log",
    "PAYMENT_STATUS": "payment_service",
    "DEVICE_RECOVERY": "device_service",
    "NOTIFICATION_RECOVERY": "notification_event_log",
    "CASE_RESOLUTION": "support_case",
}
VALID_SCOPES = set(SCOPE_SOURCE)


def verify_case_outcome(
    case_id: str,
    verification_scope: str,
    expected_outcome: str,
    action_id: str | None = None,
    transaction_id: str | None = None,
    device_id: str | None = None,
) -> dict:
    """Independently re-reads current state. Never trusts a prior tool's success flag or the model's claim."""
    if verification_scope not in VALID_SCOPES:
        raise ToolInputError(f"Unsupported verification_scope={verification_scope!r}.")

    case = get_case(case_id)
    observed_state: dict = {}
    issue_resolved = False
    mismatches: list[str] = []
    status = VStatus.INCONCLUSIVE

    if verification_scope == "ACTION_EXECUTION":
        if not action_id:
            raise ToolInputError("ACTION_EXECUTION requires action_id.")
        action = DeviceAction.objects.filter(action_id=action_id).first()
        if action is None:
            raise RecordNotFoundError(f"No action found for action_id={action_id!r}.")
        observed_state = {"execution_status": action.execution_status, "result": action.result}
        issue_resolved = action.execution_status == DeviceAction.ExecutionStatus.COMPLETED
        status = VStatus.VERIFIED if issue_resolved else VStatus.FAILED
        if not issue_resolved:
            mismatches.append(f"Expected action COMPLETED, observed {action.execution_status}.")

    elif verification_scope == "DEVICE_RECOVERY":
        if not device_id:
            raise ToolInputError("DEVICE_RECOVERY requires device_id.")
        device = device_services.get_device(device_id)
        observed_state = {"device_reachable": device.online, "notification_recovered": device.online}
        issue_resolved = device.online
        status = VStatus.VERIFIED if issue_resolved else VStatus.FAILED
        if not issue_resolved:
            mismatches.append("Expected device reachable, but device remains offline.")

    elif verification_scope == "NOTIFICATION_RECOVERY":
        if not transaction_id:
            raise ToolInputError("NOTIFICATION_RECOVERY requires transaction_id.")
        transaction = resolve_transaction(transaction_id, None)
        latest = (
            transaction.events.filter(event_type="SOUNDBOX_NOTIFICATION").order_by("-occurred_at").first()
        )
        recovered = bool(latest and latest.status == "SUCCESS")
        observed_state = {"notification_recovered": recovered}
        issue_resolved = recovered
        status = VStatus.VERIFIED if recovered else VStatus.FAILED
        if not recovered:
            mismatches.append("Expected notification delivered, but latest notification event is not SUCCESS.")

    elif verification_scope == "PAYMENT_STATUS":
        if not transaction_id:
            raise ToolInputError("PAYMENT_STATUS requires transaction_id.")
        transaction = resolve_transaction(transaction_id, None)
        observed_state = {"status": transaction.status}
        issue_resolved = transaction.status == expected_outcome
        status = (
            VStatus.VERIFIED
            if issue_resolved
            else VStatus.FAILED
            if transaction.status in ("SUCCESS", "FAILED")
            else VStatus.INCONCLUSIVE
        )
        if not issue_resolved:
            mismatches.append(f"Expected status {expected_outcome}, observed {transaction.status}.")

    else:  # CASE_RESOLUTION — reuse the most recent prior verification on this case
        latest_other = case.verifications.exclude(verification_scope="CASE_RESOLUTION").first()
        if latest_other is None:
            raise InsufficientEvidenceError(
                "No prior verification evidence exists for this case yet; verify a specific scope first."
            )
        observed_state, issue_resolved, status, mismatches = (
            latest_other.observed_state,
            latest_other.issue_resolved,
            latest_other.status,
            list(latest_other.mismatches),
        )

    record_verification(
        case=case,
        verification_scope=verification_scope,
        expected_outcome=expected_outcome,
        observed_state=observed_state,
        status=status,
        issue_resolved=issue_resolved,
        mismatches=mismatches,
    )

    resolution_transition_allowed = status == VStatus.VERIFIED and issue_resolved
    if resolution_transition_allowed:
        recommended_next_step = "CLOSE_AS_RESOLVED"
    elif status == VStatus.FAILED:
        recommended_next_step = "ESCALATE"
    elif status == VStatus.INCONCLUSIVE:
        recommended_next_step = "REQUEST_MORE_INFORMATION"
    else:
        recommended_next_step = "CONTINUE_INVESTIGATION"

    source = SCOPE_SOURCE[verification_scope]
    evidence = [{"fact": f"{k}={v}", "source": source, "observed_at": now_iso()} for k, v in observed_state.items()]

    return {
        "case_id": case.case_id,
        "action_id": action_id,
        "verification_scope": verification_scope,
        "verification_status": status,
        "issue_resolved": issue_resolved,
        "resolution_transition_allowed": resolution_transition_allowed,
        "observed_state": observed_state,
        "evidence": evidence,
        "mismatches": mismatches,
        "recommended_next_step": recommended_next_step,
    }
