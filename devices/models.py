from django.db import models

from merchants.models import Merchant


class Device(models.Model):
    device_id = models.CharField(max_length=20, unique=True, db_index=True)
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="devices")
    online = models.BooleanField(default=True)
    last_seen = models.DateTimeField()
    battery_percentage = models.PositiveSmallIntegerField(default=100)
    network_status = models.CharField(max_length=30, default="CONNECTED")
    # Seed-data control flag (not real telemetry): whether a CONNECTIVITY_CHECK
    # action should simulate a successful reconnect. Lets demo seed data pick
    # the recovery-succeeds vs. still-unreachable variant deterministically.
    recovers_on_check = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"{self.device_id} ({'online' if self.online else 'offline'})"


class DeviceAction(models.Model):
    class Action(models.TextChoices):
        CONNECTIVITY_CHECK = "CONNECTIVITY_CHECK", "Connectivity check"
        REFRESH_DEVICE_STATUS = "REFRESH_DEVICE_STATUS", "Refresh device status"
        RETRY_NOTIFICATION = "RETRY_NOTIFICATION", "Retry notification"
        RESTART_DEVICE = "RESTART_DEVICE", "Restart device"

    class ExecutionStatus(models.TextChoices):
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"
        AWAITING_APPROVAL = "AWAITING_APPROVAL", "Awaiting approval"

    action_id = models.CharField(max_length=30, unique=True, db_index=True)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="actions")
    case = models.ForeignKey(
        "support.SupportCase", on_delete=models.CASCADE, related_name="device_actions"
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    reason = models.TextField()
    idempotency_key = models.CharField(max_length=100, unique=True)
    execution_status = models.CharField(max_length=20, choices=ExecutionStatus.choices)
    result = models.JSONField(default=dict)
    approval_required = models.BooleanField(default=False)
    approval_status = models.CharField(max_length=20, null=True, blank=True)
    executed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.action_id} ({self.action} / {self.execution_status})"
