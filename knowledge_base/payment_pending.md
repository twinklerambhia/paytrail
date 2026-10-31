---
document_id: SOP_PAY_001
title: Pending Payment Procedure
issue_type: pending_payment
error_codes: []
version: "1.0"
---
Synthetic PayTrail prototype SOP. Not an actual Paytm internal policy.

## Diagnosis
A transaction with status PENDING has not yet reached a final SUCCESS or
FAILED state. Do not tell the merchant the payment succeeded or failed while
status is PENDING — only authoritative transaction records establish status.

## Approved next step
Explain that confirmation is still in progress and ask the merchant to wait
for the standard settlement window before retrying. Do not initiate a new
payment attempt or any retry on the merchant's behalf.

## Escalation
If the transaction remains PENDING past the expected confirmation window,
create a support case with issue_type=pending_payment and assigned_team
PAYMENTS_OPS so a human can check with the payment gateway.
