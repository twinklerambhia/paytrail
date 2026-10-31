---
document_id: SOP_ESC_001
title: Human Escalation Policy
issue_type: unknown
error_codes: []
version: "1.0"
---
Synthetic PayTrail prototype SOP. Not an actual Paytm internal policy.

## When to escalate
Escalate (manage_support_case with target_status=ESCALATED and an
assigned_team) whenever any of the following is true:
- A diagnostic or recovery action was attempted and verification still
  shows the issue unresolved.
- The only remaining allowed action requires human approval (for example
  RESTART_DEVICE).
- Available evidence is insufficient to safely conclude or act further.
- The agent has reached its bounded tool-call limit for the turn without
  reaching a verified resolution.

## Team routing
- soundbox_no_alert, unresolved after diagnostics -> DEVICE_SUPPORT
- pending_payment, past expected window -> PAYMENTS_OPS
- payment_failed with disputed customer-side deduction -> PAYMENTS_OPS
- payment_status_dispute, settlement_query -> PAYMENTS_OPS

## What an escalation must include
Merchant id, transaction id (if any), issue summary, evidence gathered,
actions attempted and their results, and the verification outcome. Never
escalate with an empty evidence trail.
