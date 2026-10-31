from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from devices.models import Device, DeviceAction
from merchants.models import Merchant
from payments.models import Transaction, TransactionEvent
from support.models import SupportCase, SupportCaseNote, VerificationRecord

# Synthetic demo data only — not real Paytm records. Re-runnable: every
# record is looked up by its natural key first (update_or_create), and
# the pre-seeded case history skips re-creating child rows once a case
# already exists, so running this command twice never duplicates anything.

SOUNDBOX_NO_ALERT_CASES = [
    dict(merchant_id="M100", business_name="Sharma General Store", phone="9800000000", lang="hi",
         txn_id="TXN1002", amount="850.00", device_id="SB100", recovers=False, error_code="DEVICE_UNREACHABLE"),
    dict(merchant_id="M101", business_name="Patil Tea Stall", phone="9800000003", lang="mr",
         txn_id="TXN1003", amount="500.00", device_id="SB101", recovers=True, error_code="DEVICE_UNREACHABLE"),
    dict(merchant_id="M104", business_name="Khan Mobile Repairs", phone="9800000004", lang="hi",
         txn_id="TXN1004", amount="1250.00", device_id="SB104", recovers=True, error_code="NOTIFICATION_TIMEOUT"),
    dict(merchant_id="M105", business_name="Nair Supermarket", phone="9800000005", lang="en",
         txn_id="TXN1005", amount="275.50", device_id="SB105", recovers=False, error_code="DEVICE_UNREACHABLE"),
]

PENDING_PAYMENT_CASES = [
    dict(merchant_id="M102", business_name="Verma Kirana", phone="9800000001", lang="en", txn_id="TXN2001", amount="300.00"),
    dict(merchant_id="M106", business_name="Joshi Xerox Centre", phone="9800000006", lang="mr", txn_id="TXN2002", amount="120.00"),
    dict(merchant_id="M107", business_name="Reddy Dairy Farm", phone="9800000007", lang="en", txn_id="TXN2003", amount="980.00"),
]

PAYMENT_FAILED_CASES = [
    dict(merchant_id="M103", business_name="Iyer Fruit Mart", phone="9800000002", lang="mr",
         txn_id="TXN3001", amount="450.00", error_code="BANK_DECLINE"),
    dict(merchant_id="M108", business_name="Gupta Electronics", phone="9800000008", lang="hi",
         txn_id="TXN3002", amount="2200.00", error_code="INSUFFICIENT_FUNDS"),
    dict(merchant_id="M109", business_name="Das Stationery", phone="9800000009", lang="en",
         txn_id="TXN3003", amount="65.00", error_code="GATEWAY_TIMEOUT"),
]


class Command(BaseCommand):
    help = "Seed synthetic merchants/transactions/devices + case history for PayTrail demo scenarios A/B/C."

    def handle(self, *args, **options):
        now = timezone.now()

        for spec in SOUNDBOX_NO_ALERT_CASES:
            self._soundbox_no_alert(now, **spec)
        for spec in PENDING_PAYMENT_CASES:
            self._pending_payment(now, **spec)
        for spec in PAYMENT_FAILED_CASES:
            self._payment_failed(now, **spec)

        self._seed_case_history(now)

        total = len(SOUNDBOX_NO_ALERT_CASES) + len(PENDING_PAYMENT_CASES) + len(PAYMENT_FAILED_CASES)
        self.stdout.write(self.style.SUCCESS(
            f"Seed complete: {total} merchants/transactions "
            f"({len(SOUNDBOX_NO_ALERT_CASES)} soundbox, {len(PENDING_PAYMENT_CASES)} pending, "
            f"{len(PAYMENT_FAILED_CASES)} failed), plus pre-seeded case history."
        ))

    # -- shared helpers ----------------------------------------------------

    def _merchant(self, merchant_id, business_name, phone, lang) -> Merchant:
        merchant, _ = Merchant.objects.update_or_create(
            merchant_id=merchant_id,
            defaults={"business_name": business_name, "phone": phone, "preferred_language": lang},
        )
        return merchant

    def _transaction(self, merchant, txn_id, amount, status, now, minutes_ago) -> Transaction:
        txn, _ = Transaction.objects.update_or_create(
            transaction_id=txn_id,
            defaults={
                "merchant": merchant,
                "amount": amount,
                "currency": "INR",
                "status": status,
                "created_at": now - timedelta(minutes=minutes_ago),
                "status_updated_at": now - timedelta(minutes=minutes_ago),
                "source": "payment_service",
            },
        )
        return txn

    # -- scenario builders ---------------------------------------------------

    def _soundbox_no_alert(self, now, merchant_id, business_name, phone, lang, txn_id, amount, device_id, recovers, error_code):
        """Payment SUCCESS, Soundbox notification FAILED."""
        merchant = self._merchant(merchant_id, business_name, phone, lang)
        Device.objects.update_or_create(
            device_id=device_id,
            defaults={
                "merchant": merchant,
                "online": False,
                "last_seen": now - timedelta(minutes=20),
                "battery_percentage": 60 + (abs(hash(device_id)) % 35),
                "network_status": "DISCONNECTED",
                "recovers_on_check": recovers,
            },
        )
        txn = self._transaction(merchant, txn_id, amount, Transaction.Status.SUCCESS, now, minutes_ago=15)
        txn.events.all().delete()
        TransactionEvent.objects.create(
            transaction=txn, event_type="PAYMENT_CONFIRMED", status="SUCCESS",
            occurred_at=now - timedelta(minutes=15), source="payment_event_log",
        )
        TransactionEvent.objects.create(
            transaction=txn, event_type="SOUNDBOX_NOTIFICATION", status="FAILED", error_code=error_code,
            occurred_at=now - timedelta(minutes=14, seconds=55), source="notification_event_log",
        )

    def _pending_payment(self, now, merchant_id, business_name, phone, lang, txn_id, amount):
        """Payment still PENDING."""
        merchant = self._merchant(merchant_id, business_name, phone, lang)
        txn = self._transaction(merchant, txn_id, amount, Transaction.Status.PENDING, now, minutes_ago=5)
        txn.events.all().delete()
        TransactionEvent.objects.create(
            transaction=txn, event_type="PAYMENT_INITIATED", status="PENDING",
            occurred_at=now - timedelta(minutes=5), source="payment_event_log",
        )

    def _payment_failed(self, now, merchant_id, business_name, phone, lang, txn_id, amount, error_code):
        """Payment FAILED — merchant may claim customer was charged."""
        merchant = self._merchant(merchant_id, business_name, phone, lang)
        txn = self._transaction(merchant, txn_id, amount, Transaction.Status.FAILED, now, minutes_ago=10)
        txn.events.all().delete()
        TransactionEvent.objects.create(
            transaction=txn, event_type="PAYMENT_FAILED", status="FAILED", error_code=error_code,
            occurred_at=now - timedelta(minutes=10), source="payment_event_log",
        )

    # -- pre-seeded case history: dashboard has content before any live chat --

    def _seed_case_history(self, now):
        self._resolved_soundbox_case(now)
        self._escalated_soundbox_case(now)
        self._escalated_payment_dispute(now)

    def _resolved_soundbox_case(self, now):
        merchant = Merchant.objects.get(merchant_id="M101")
        txn = Transaction.objects.get(transaction_id="TXN1003")
        device = Device.objects.get(device_id="SB101")
        case, created = SupportCase.objects.update_or_create(
            case_id="CASEHIST01",
            defaults={
                "merchant": merchant, "transaction": txn,
                "issue_type": SupportCase.IssueType.SOUNDBOX_NO_ALERT,
                "status": SupportCase.Status.RESOLVED, "priority": SupportCase.Priority.MEDIUM,
                "summary": "Soundbox offline after successful payment; recovered after a connectivity check.",
                "create_idempotency_key": "SEED-CASEHIST01",
            },
        )
        if not created:
            return
        DeviceAction.objects.create(
            action_id="ACTHIST01", device=device, case=case, action="CONNECTIVITY_CHECK",
            reason="Device offline after SUCCESS payment with FAILED notification.",
            idempotency_key="SEED-ACTHIST01", execution_status="COMPLETED",
            result={"device_reachable": True}, executed_at=now - timedelta(hours=2),
        )
        VerificationRecord.objects.create(
            case=case, verification_scope="DEVICE_RECOVERY", expected_outcome="DEVICE_REACHABLE",
            observed_state={"device_reachable": True, "notification_recovered": True},
            status="VERIFIED", issue_resolved=True, mismatches=[],
        )
        SupportCaseNote.objects.create(
            case=case, note="Device reconnected after CONNECTIVITY_CHECK; verified and closed as resolved."
        )

    def _escalated_soundbox_case(self, now):
        merchant = Merchant.objects.get(merchant_id="M100")
        txn = Transaction.objects.get(transaction_id="TXN1002")
        device = Device.objects.get(device_id="SB100")
        case, created = SupportCase.objects.update_or_create(
            case_id="CASEHIST02",
            defaults={
                "merchant": merchant, "transaction": txn,
                "issue_type": SupportCase.IssueType.SOUNDBOX_NO_ALERT,
                "status": SupportCase.Status.ESCALATED, "priority": SupportCase.Priority.HIGH,
                "assigned_team": "DEVICE_SUPPORT",
                "summary": "Soundbox remained unreachable after a connectivity check.",
                "create_idempotency_key": "SEED-CASEHIST02",
            },
        )
        if not created:
            return
        DeviceAction.objects.create(
            action_id="ACTHIST02", device=device, case=case, action="CONNECTIVITY_CHECK",
            reason="Device offline after SUCCESS payment with FAILED notification.",
            idempotency_key="SEED-ACTHIST02", execution_status="COMPLETED",
            result={"device_reachable": False, "error_code": "DEVICE_UNREACHABLE"},
            executed_at=now - timedelta(hours=1),
        )
        VerificationRecord.objects.create(
            case=case, verification_scope="DEVICE_RECOVERY", expected_outcome="DEVICE_REACHABLE",
            observed_state={"device_reachable": False, "notification_recovered": False},
            status="FAILED", issue_resolved=False,
            mismatches=["Expected device reachable, but device remains offline."],
        )
        SupportCaseNote.objects.create(
            case=case, note="Still unreachable after diagnostic; assigned to Device Support."
        )

    def _escalated_payment_dispute(self, now):
        merchant = Merchant.objects.get(merchant_id="M103")
        txn = Transaction.objects.get(transaction_id="TXN3001")
        case, created = SupportCase.objects.update_or_create(
            case_id="CASEHIST03",
            defaults={
                "merchant": merchant, "transaction": txn,
                "issue_type": SupportCase.IssueType.PAYMENT_FAILED,
                "status": SupportCase.Status.ESCALATED, "priority": SupportCase.Priority.HIGH,
                "assigned_team": "PAYMENTS_OPS",
                "summary": "Customer reports a deduction despite a platform-confirmed decline.",
                "create_idempotency_key": "SEED-CASEHIST03",
            },
        )
        if not created:
            return
        SupportCaseNote.objects.create(
            case=case,
            note="Platform shows BANK_DECLINE; bank-side deduction can't be confirmed from here. Escalated to Payments Ops.",
        )
