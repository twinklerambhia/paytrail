---
document_id: SOP_SB_002
title: Notification Failure and Retry Prerequisites
issue_type: soundbox_no_alert
error_codes: [DEVICE_UNREACHABLE, NOTIFICATION_TIMEOUT]
version: "1.0"
---
Synthetic PayTrail prototype SOP. Not an actual Paytm internal policy.

## Diagnosis
A SOUNDBOX_NOTIFICATION event with status FAILED and error_code
DEVICE_UNREACHABLE means the notification could not be delivered because
the device was not reachable at send time — not that the payment failed.

## RETRY_NOTIFICATION prerequisites
RETRY_NOTIFICATION is only permitted when the device is currently reachable.
Retrying against a device that is still offline is pointless and denied by
policy — run CONNECTIVITY_CHECK first and confirm the device is online
before requesting a retry.

## Approved next step
Once the device is confirmed reachable, execute_device_action with
action=RETRY_NOTIFICATION, then verify with verify_case_outcome using
verification_scope=NOTIFICATION_RECOVERY before telling the merchant the
alert was resent successfully.
