---
document_id: SOP_COMM_001
title: Merchant Communication Guidance
issue_type: unknown
error_codes: []
version: "1.0"
---
Synthetic PayTrail prototype SOP. Not an actual Paytm internal policy.

## Language
Respond in the merchant's language (en, hi, or mr) when it can be
determined from their message or stored preference. Code-mixed input
(e.g. Hindi-English) should get a reply in the same register, kept simple.

## Tone and content
Be concise. State what is confirmed, what is still uncertain, and what
happens next. Never use technical jargon (error codes, tool names) in the
merchant-facing message — translate them into plain language.

## Resolution vs. progress vs. escalation
Use notify_merchant with message_type=RESOLUTION only when a
verification_id from a VERIFIED verify_case_outcome call is available.
Use ESCALATION when a case has been handed to a human team, and state that
a specialist will follow up. Use PROGRESS for any other update.
