---
document_id: SOP_PAY_002
title: Confirmed Payment Failure Procedure
issue_type: payment_failed
error_codes: [BANK_DECLINE, INSUFFICIENT_FUNDS, GATEWAY_TIMEOUT]
version: "1.0"
---
Synthetic PayTrail prototype SOP. Not an actual Paytm internal policy.

## Diagnosis
A transaction with status FAILED did not complete. The platform's own event
log is authoritative for the platform-side outcome. Whether the customer's
bank debited and later reversed funds is a bank-side fact PayTrail cannot
observe directly — do not confirm or deny a customer-side deduction.

## When the merchant says the customer was charged anyway
Separate confirmed platform facts (transaction status, failure event, error
code) from unknown bank-side facts (whether a debit/reversal happened on the
customer's bank statement). Never claim a refund or reversal occurred —
PayTrail has no tool that performs or confirms refunds.

## Approved next step
Explain the platform-confirmed failure reason in plain language. If the
bank-side outcome cannot be established from available evidence, escalate
to PAYMENTS_OPS with the transaction evidence attached.
