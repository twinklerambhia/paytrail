from django.db import models

from support.models import SupportCase, VerificationRecord


class ToolExecution(models.Model):
    """Generic audit log for every agent tool call, regardless of tool."""

    request_id = models.CharField(max_length=40, unique=True)
    tool_name = models.CharField(max_length=50)
    case = models.ForeignKey(
        SupportCase, null=True, blank=True, on_delete=models.SET_NULL, related_name="tool_executions"
    )
    arguments = models.JSONField()
    ok = models.BooleanField()
    result = models.JSONField(null=True, blank=True)
    error_code = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.tool_name} ({'ok' if self.ok else 'error'}) @ {self.created_at}"


class MerchantNotification(models.Model):
    class MessageType(models.TextChoices):
        PROGRESS = "PROGRESS", "Progress"
        RESOLUTION = "RESOLUTION", "Resolution"
        ESCALATION = "ESCALATION", "Escalation"

    notification_id = models.CharField(max_length=30, unique=True)
    case = models.ForeignKey(SupportCase, on_delete=models.CASCADE, related_name="notifications")
    language = models.CharField(max_length=5)
    message = models.TextField()
    message_type = models.CharField(max_length=20, choices=MessageType.choices)
    verification = models.ForeignKey(
        VerificationRecord, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.notification_id} ({self.message_type}) -> {self.case.case_id}"
