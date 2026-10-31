---
document_id: SOP_SB_000
title: Successful Payment, Soundbox No Alert
issue_type: soundbox_no_alert
error_codes: [DEVICE_UNREACHABLE]
version: "1.0"
---
Synthetic PayTrail prototype SOP. Not an actual Paytm internal policy.

## Diagnosis
Payment success and Soundbox notification delivery are two separate states.
A SUCCESS transaction with a FAILED SOUNDBOX_NOTIFICATION event means the
money moved but the device did not announce it — this is a notification
delivery problem, not a payment problem. Never tell the merchant the payment
failed when transaction status is SUCCESS.

## Approved next step
Confirm the payment succeeded first. Then investigate the linked device
(see Soundbox Connectivity Troubleshooting, SOP_SB_001) before claiming
anything about why the alert did not play.
