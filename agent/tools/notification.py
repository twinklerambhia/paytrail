import uuid

from agent.errors import PolicyDeniedError, RecordNotFoundError, ToolInputError
from agent.models import MerchantNotification
from support.models import VerificationRecord
from support.services import get_case

MESSAGE_TYPES = {"PROGRESS", "RESOLUTION", "ESCALATION"}


def notify_merchant(
    case_id: str,
    language: str,
    message: str,
    message_type: str,
    verification_id: str | None = None,
) -> dict:
    """Record a merchant-facing update. RESOLUTION requires a VERIFIED verification record; mock log only."""
    if language not in ("en", "hi", "mr"):
        raise ToolInputError(f"Unsupported language={language!r}.")
    if message_type not in MESSAGE_TYPES:
        raise ToolInputError(f"Unsupported message_type={message_type!r}.")
    if not message or not message.strip():
        raise ToolInputError("message is required.")

    case = get_case(case_id)

    verification = None
    if message_type == "RESOLUTION":
        if not verification_id:
            raise PolicyDeniedError("RESOLUTION messages require a verification_id.")
        try:
            verification = VerificationRecord.objects.get(pk=verification_id, case=case)
        except (VerificationRecord.DoesNotExist, ValueError):
            raise RecordNotFoundError(f"No verification record {verification_id!r} found for this case.")
        if verification.status != VerificationRecord.VerificationStatus.VERIFIED or not verification.issue_resolved:
            raise PolicyDeniedError("RESOLUTION requires a VERIFIED verification with issue_resolved=True.")

    notification = MerchantNotification.objects.create(
        notification_id=f"MSG{uuid.uuid4().hex[:8].upper()}",
        case=case,
        language=language,
        message=message,
        message_type=message_type,
        verification=verification,
    )

    return {
        "notification_id": notification.notification_id,
        "case_id": case.case_id,
        "message_type": notification.message_type,
        "language": notification.language,
        "delivery_mode": "MOCK_LOG",
        "delivery_status": "RECORDED",
        "created_at": notification.created_at.isoformat(),
    }
