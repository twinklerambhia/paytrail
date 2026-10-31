from django.db import models

from merchants.models import Merchant


class Transaction(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"

    transaction_id = models.CharField(max_length=30, unique=True, db_index=True)
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="transactions")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="INR")
    status = models.CharField(max_length=10, choices=Status.choices)
    created_at = models.DateTimeField()
    status_updated_at = models.DateTimeField()
    source = models.CharField(max_length=50, default="payment_service")

    def __str__(self) -> str:
        return f"{self.transaction_id} ({self.status})"


class TransactionEvent(models.Model):
    """Single merged log for payment + notification lifecycle events.

    event_type examples: PAYMENT_INITIATED, PAYMENT_CONFIRMED, PAYMENT_FAILED,
    SOUNDBOX_NOTIFICATION, BANK_DEBIT_STATUS_UNKNOWN.
    """

    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=50)
    status = models.CharField(max_length=20)
    error_code = models.CharField(max_length=50, null=True, blank=True)
    occurred_at = models.DateTimeField()
    source = models.CharField(max_length=50)

    class Meta:
        ordering = ["occurred_at"]

    def __str__(self) -> str:
        return f"{self.transaction.transaction_id} / {self.event_type} / {self.status}"
