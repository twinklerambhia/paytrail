from django.db import models

from merchants.models import Merchant
from payments.models import Transaction


class SupportCase(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        AWAITING_APPROVAL = "AWAITING_APPROVAL", "Awaiting approval"
        ESCALATED = "ESCALATED", "Escalated"
        RESOLVED = "RESOLVED", "Resolved"
        CLOSED = "CLOSED", "Closed"

    class IssueType(models.TextChoices):
        PENDING_PAYMENT = "pending_payment", "Pending payment"
        PAYMENT_FAILED = "payment_failed", "Payment failed"
        SOUNDBOX_NO_ALERT = "soundbox_no_alert", "Soundbox no alert"
        PAYMENT_STATUS_DISPUTE = "payment_status_dispute", "Payment status dispute"
        SETTLEMENT_QUERY = "settlement_query", "Settlement query"
        UNKNOWN = "unknown", "Unknown"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent"

    case_id = models.CharField(max_length=20, unique=True, db_index=True)
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="cases")
    transaction = models.ForeignKey(
        Transaction, null=True, blank=True, on_delete=models.SET_NULL, related_name="cases"
    )
    issue_type = models.CharField(max_length=30, choices=IssueType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    assigned_team = models.CharField(max_length=50, null=True, blank=True)
    summary = models.CharField(max_length=300, null=True, blank=True)
    details = models.TextField(null=True, blank=True)
    evidence_refs = models.JSONField(default=list, blank=True)
    create_idempotency_key = models.CharField(max_length=100, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.case_id} ({self.status})"


class SupportCaseNote(models.Model):
    case = models.ForeignKey(SupportCase, on_delete=models.CASCADE, related_name="notes")
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"note on {self.case.case_id} @ {self.created_at}"


class VerificationRecord(models.Model):
    """Audit record written every time verify_case_outcome runs.

    Never mutates Transaction/Device/SupportCase rows itself; it is the
    evidence a RESOLVED transition or a RESOLUTION notification checks for.
    """

    class VerificationStatus(models.TextChoices):
        VERIFIED = "VERIFIED", "Verified"
        FAILED = "FAILED", "Failed"
        PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED", "Partially verified"
        INCONCLUSIVE = "INCONCLUSIVE", "Inconclusive"

    class Scope(models.TextChoices):
        ACTION_EXECUTION = "ACTION_EXECUTION", "Action execution"
        PAYMENT_STATUS = "PAYMENT_STATUS", "Payment status"
        DEVICE_RECOVERY = "DEVICE_RECOVERY", "Device recovery"
        NOTIFICATION_RECOVERY = "NOTIFICATION_RECOVERY", "Notification recovery"
        CASE_RESOLUTION = "CASE_RESOLUTION", "Case resolution"

    case = models.ForeignKey(SupportCase, on_delete=models.CASCADE, related_name="verifications")
    verification_scope = models.CharField(max_length=30, choices=Scope.choices)
    expected_outcome = models.CharField(max_length=200)
    observed_state = models.JSONField()
    status = models.CharField(max_length=20, choices=VerificationStatus.choices)
    issue_resolved = models.BooleanField()
    mismatches = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.case.case_id} / {self.verification_scope} / {self.status}"
