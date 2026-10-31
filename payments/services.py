from agent.errors import AmbiguousReferenceError, RecordNotFoundError, ToolInputError

from .models import Transaction


def resolve_transaction(transaction_id: str | None, merchant_id: str | None) -> Transaction:
    if not transaction_id and not merchant_id:
        raise ToolInputError("At least one of transaction_id or merchant_id is required.")

    if transaction_id:
        try:
            return Transaction.objects.select_related("merchant").get(transaction_id=transaction_id)
        except Transaction.DoesNotExist:
            raise RecordNotFoundError(f"No transaction found for transaction_id={transaction_id!r}.")

    candidates = list(
        Transaction.objects.select_related("merchant")
        .filter(merchant__merchant_id=merchant_id)
        .order_by("-created_at")[:2]
    )
    if not candidates:
        raise RecordNotFoundError(f"No transaction found for merchant_id={merchant_id!r}.")
    if len(candidates) > 1:
        raise AmbiguousReferenceError(
            f"merchant_id={merchant_id!r} matches multiple transactions; supply transaction_id."
        )
    return candidates[0]


def transaction_to_dict(transaction: Transaction) -> dict:
    return {
        "transaction_id": transaction.transaction_id,
        "merchant_id": transaction.merchant.merchant_id,
        "amount": float(transaction.amount),
        "currency": transaction.currency,
        "status": transaction.status,
        "created_at": transaction.created_at.isoformat(),
        "status_updated_at": transaction.status_updated_at.isoformat(),
        "source": transaction.source,
    }


def events_for_transaction(transaction: Transaction) -> list[dict]:
    return [
        {
            "event_type": event.event_type,
            "status": event.status,
            "error_code": event.error_code,
            "occurred_at": event.occurred_at.isoformat(),
            "source": event.source,
        }
        for event in transaction.events.all()
    ]
