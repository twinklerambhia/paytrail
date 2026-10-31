from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from devices.models import Device
from merchants.models import Merchant
from payments.models import Transaction, TransactionEvent

# Synthetic demo data only — not real Paytm records. Re-runnable: every
# record is looked up by its natural key first (get_or_create / update).


class Command(BaseCommand):
    help = "Seed synthetic merchants/transactions/devices for PayTrail demo scenarios A/B/C."

    def handle(self, *args, **options):
        now = timezone.now()

        self._scenario_a(now, recover=False, merchant_id="M100", business_name="Sharma General Store",
                          txn_id="TXN1002", amount="850.00", device_id="SB100")
        self._scenario_a(now, recover=True, merchant_id="M101", business_name="Patil Tea Stall",
                          txn_id="TXN1003", amount="500.00", device_id="SB101")
        self._scenario_b(now)
        self._scenario_c(now)

        self.stdout.write(self.style.SUCCESS("Seed complete."))

    def _scenario_a(self, now, recover, merchant_id, business_name, txn_id, amount, device_id):
        """Payment SUCCESS, Soundbox notification FAILED (DEVICE_UNREACHABLE)."""
        merchant, _ = Merchant.objects.update_or_create(
            merchant_id=merchant_id,
            defaults={"business_name": business_name, "phone": "9800000000", "preferred_language": "hi"},
        )
        Device.objects.update_or_create(
            device_id=device_id,
            defaults={
                "merchant": merchant,
                "online": False,
                "last_seen": now - timedelta(minutes=20),
                "battery_percentage": 75,
                "network_status": "DISCONNECTED",
                "recovers_on_check": recover,
            },
        )
        txn, _ = Transaction.objects.update_or_create(
            transaction_id=txn_id,
            defaults={
                "merchant": merchant,
                "amount": amount,
                "currency": "INR",
                "status": Transaction.Status.SUCCESS,
                "created_at": now - timedelta(minutes=15),
                "status_updated_at": now - timedelta(minutes=15),
                "source": "payment_service",
            },
        )
        txn.events.all().delete()
        TransactionEvent.objects.create(
            transaction=txn, event_type="PAYMENT_CONFIRMED", status="SUCCESS",
            occurred_at=now - timedelta(minutes=15), source="payment_event_log",
        )
        TransactionEvent.objects.create(
            transaction=txn, event_type="SOUNDBOX_NOTIFICATION", status="FAILED",
            error_code="DEVICE_UNREACHABLE", occurred_at=now - timedelta(minutes=14, seconds=55),
            source="notification_event_log",
        )

    def _scenario_b(self, now):
        """Payment still PENDING."""
        merchant, _ = Merchant.objects.update_or_create(
            merchant_id="M102",
            defaults={"business_name": "Verma Kirana", "phone": "9800000001", "preferred_language": "en"},
        )
        txn, _ = Transaction.objects.update_or_create(
            transaction_id="TXN2001",
            defaults={
                "merchant": merchant,
                "amount": "300.00",
                "currency": "INR",
                "status": Transaction.Status.PENDING,
                "created_at": now - timedelta(minutes=5),
                "status_updated_at": now - timedelta(minutes=5),
                "source": "payment_service",
            },
        )
        txn.events.all().delete()
        TransactionEvent.objects.create(
            transaction=txn, event_type="PAYMENT_INITIATED", status="PENDING",
            occurred_at=now - timedelta(minutes=5), source="payment_event_log",
        )

    def _scenario_c(self, now):
        """Payment FAILED (BANK_DECLINE) — merchant claims customer was charged."""
        merchant, _ = Merchant.objects.update_or_create(
            merchant_id="M103",
            defaults={"business_name": "Iyer Fruit Mart", "phone": "9800000002", "preferred_language": "mr"},
        )
        txn, _ = Transaction.objects.update_or_create(
            transaction_id="TXN3001",
            defaults={
                "merchant": merchant,
                "amount": "450.00",
                "currency": "INR",
                "status": Transaction.Status.FAILED,
                "created_at": now - timedelta(minutes=10),
                "status_updated_at": now - timedelta(minutes=10),
                "source": "payment_service",
            },
        )
        txn.events.all().delete()
        TransactionEvent.objects.create(
            transaction=txn, event_type="PAYMENT_FAILED", status="FAILED",
            error_code="BANK_DECLINE", occurred_at=now - timedelta(minutes=10),
            source="payment_event_log",
        )
