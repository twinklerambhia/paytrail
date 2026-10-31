import uuid

from django.utils import timezone

from agent.errors import PolicyDeniedError, RecordNotFoundError, ToolInputError

from .models import Device, DeviceAction

# MVP allowlist. RESTART_DEVICE always requires human approval; RETRY_NOTIFICATION
# requires the device to be currently reachable.
ALLOWED_ACTIONS = {
    "CONNECTIVITY_CHECK",
    "REFRESH_DEVICE_STATUS",
    "RETRY_NOTIFICATION",
    "RESTART_DEVICE",
}
ACTIONS_REQUIRING_APPROVAL = {"RESTART_DEVICE"}


def get_device(device_id: str) -> Device:
    try:
        return Device.objects.select_related("merchant").get(device_id=device_id)
    except Device.DoesNotExist:
        raise RecordNotFoundError(f"No device found for device_id={device_id!r}.")


def device_summary(device: Device) -> dict:
    return {
        "device_id": device.device_id,
        "online": device.online,
        "last_seen": device.last_seen.isoformat(),
        "source": "device_service",
    }


def device_health_status(device: Device) -> str:
    if not device.online or device.network_status != "CONNECTED":
        return "UNHEALTHY"
    if device.battery_percentage < 20:
        return "DEGRADED"
    return "HEALTHY"


def inspect(device: Device, inspection_type: str) -> dict:
    valid_types = {"connectivity", "network", "battery", "notification_history", "full_health_check"}
    if inspection_type not in valid_types:
        raise ToolInputError(f"Unsupported inspection_type={inspection_type!r}.")

    data = {
        "device_id": device.device_id,
        "inspection_type": inspection_type,
        "health_status": device_health_status(device),
        "observed_at": timezone.now().isoformat(),
        "evidence_sources": ["device_service"],
    }
    if inspection_type in ("connectivity", "network", "full_health_check"):
        data["connectivity"] = {
            "online": device.online,
            "network_status": device.network_status,
            "last_seen": device.last_seen.isoformat(),
        }
    if inspection_type in ("battery", "full_health_check"):
        data["battery"] = {
            "percentage": device.battery_percentage,
            "status": "LOW" if device.battery_percentage < 20 else "NORMAL",
        }
    if inspection_type in ("notification_history", "full_health_check"):
        data["notification_history"] = []
    return data


def execute_action(
    device: Device,
    action: str,
    case,
    reason: str,
    idempotency_key: str,
    transaction=None,
) -> dict:
    if action not in ALLOWED_ACTIONS:
        raise ToolInputError(f"Unsupported action={action!r}.")

    existing = DeviceAction.objects.filter(idempotency_key=idempotency_key).first()
    if existing is not None:
        return _action_to_dict(existing)

    if action in ACTIONS_REQUIRING_APPROVAL:
        # Not an error: a valid outcome the agent must report as unexecuted,
        # never as "done". No DeviceAction row — nothing ran yet.
        return {
            "action_id": None,
            "device_id": device.device_id,
            "case_id": case.case_id,
            "action": action,
            "execution_status": DeviceAction.ExecutionStatus.AWAITING_APPROVAL,
            "result": None,
            "approval": {
                "required": True,
                "status": "PENDING",
                "approval_request_id": f"APR{uuid.uuid4().hex[:6].upper()}",
            },
            "executed_at": None,
        }

    if action == "RETRY_NOTIFICATION" and not device.online:
        raise PolicyDeniedError(
            "RETRY_NOTIFICATION requires a reachable device; device is currently offline."
        )

    # Deterministic, seed-controlled simulation — never a real device call.
    if action == "CONNECTIVITY_CHECK":
        if device.recovers_on_check and not device.online:
            device.online = True
            device.network_status = "CONNECTED"
            device.last_seen = timezone.now()
            device.save(update_fields=["online", "network_status", "last_seen"])
        reachable = device.online
        result = {
            "device_reachable": reachable,
            "error_code": None if reachable else "DEVICE_UNREACHABLE",
        }
    elif action == "REFRESH_DEVICE_STATUS":
        result = {"online": device.online, "network_status": device.network_status}
    else:  # RETRY_NOTIFICATION, device already confirmed online above
        result = {"notification_retried": True}

    device_action = DeviceAction.objects.create(
        action_id=f"ACT{uuid.uuid4().hex[:8].upper()}",
        device=device,
        case=case,
        action=action,
        reason=reason,
        idempotency_key=idempotency_key,
        execution_status=DeviceAction.ExecutionStatus.COMPLETED,
        result=result,
        approval_required=False,
        approval_status="NOT_REQUIRED",
    )
    return _action_to_dict(device_action)


def _action_to_dict(device_action: DeviceAction) -> dict:
    return {
        "action_id": device_action.action_id,
        "device_id": device_action.device.device_id,
        "case_id": device_action.case.case_id,
        "action": device_action.action,
        "execution_status": device_action.execution_status,
        "result": device_action.result,
        "approval": {
            "required": device_action.approval_required,
            "status": device_action.approval_status or "NOT_REQUIRED",
        },
        "executed_at": device_action.executed_at.isoformat(),
    }
