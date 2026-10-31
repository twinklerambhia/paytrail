from agent.errors import ToolInputError
from devices import services as device_services
from payments.services import resolve_transaction
from support.services import get_case


def inspect_device(
    device_id: str,
    inspection_type: str,
    transaction_id: str | None = None,
) -> dict:
    """Read-only, deeper device inspection. Does not change device state."""
    device = device_services.get_device(device_id)
    data = device_services.inspect(device, inspection_type)
    if transaction_id:
        resolve_transaction(transaction_id, None)  # validates the correlation id exists
        data["correlated_transaction_id"] = transaction_id
    return data


def execute_device_action(
    device_id: str,
    action: str,
    case_id: str,
    reason: str,
    idempotency_key: str,
    transaction_id: str | None = None,
) -> dict:
    """State-changing diagnostic/recovery boundary. Backend is authoritative, not the model."""
    if not reason or not reason.strip():
        raise ToolInputError("reason is required and must be evidence-based.")
    device = device_services.get_device(device_id)
    case = get_case(case_id)
    transaction = resolve_transaction(transaction_id, None) if transaction_id else None
    return device_services.execute_action(
        device=device,
        action=action,
        case=case,
        reason=reason,
        idempotency_key=idempotency_key,
        transaction=transaction,
    )
