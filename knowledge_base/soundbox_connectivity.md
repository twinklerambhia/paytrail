---
document_id: SOP_SB_001
title: Soundbox Connectivity Troubleshooting
issue_type: soundbox_no_alert
error_codes: [DEVICE_UNREACHABLE]
version: "1.0"
---
Synthetic PayTrail prototype SOP. Not an actual Paytm internal policy.

## Diagnosis
If inspect_device shows the device offline or DISCONNECTED, a connectivity
problem is the likely cause of a missed notification.

## Approved action
Run a CONNECTIVITY_CHECK diagnostic via execute_device_action. A COMPLETED
execution_status only means the diagnostic ran — it does not mean the
device is reachable again. Always read the diagnostic's own result
(device_reachable) before drawing a conclusion.

## Verification
After the diagnostic, independently verify with verify_case_outcome using
verification_scope=DEVICE_RECOVERY. Only report the Soundbox as working
again if verification confirms the device is reachable.

## Escalation
If the device remains unreachable after one CONNECTIVITY_CHECK, do not
retry indefinitely. Assign the case to DEVICE_SUPPORT via manage_support_case
with the diagnostic result and verification evidence attached.
