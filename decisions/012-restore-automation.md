# 012: automate RDS/Redshift resume on platform host boot, leave credential export manual

Stage: S4 · Date: 2026-11-22 · Author: student · Drafted by agent: yes

## Choice

Automate RDS start and Redshift resume via a systemd service (`lab-restore.service`) that runs once on platform host boot. Leave credential export as a documented manual step.

## Rejected alternative

Automate everything including credential export using a stored IAM long-lived key injected via EC2 user-data or SSM Parameter Store. This would eliminate the manual credential step entirely.

## Why

Storing a long-lived IAM key (even in SSM) in a Learner Lab account is a security risk: the account is shared, the key would have LabRole-level permissions, and the lab environment is not production-hardened. The session-token approach (copy-paste from Start Lab) is intentionally short-lived and scoped. The two-minute manual step is acceptable toil for the security boundary it preserves. RDS start and Redshift resume, by contrast, are safe to automate: they are idempotent (AWS ignores the call if already running), have no credential-exposure risk (the platform host uses its EC2 instance profile), and accounted for the longest wall-clock wait (~9 min combined) during the manual restore.

## What would show this was wrong

If the Learner Lab ever provisions persistent IAM credentials on the host (e.g., via instance profile rotation) that survive sessions, the manual credential step becomes unnecessary and the decision should be revisited. Alternatively, if the boot script starts causing billing surprises by resuming Redshift before the student is ready to use it, it should be gated behind a manual trigger instead.
