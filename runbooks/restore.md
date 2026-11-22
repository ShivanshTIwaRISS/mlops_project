# Runbook: restore lab service after Learner Lab session end

Owner: student · Last run: 2026-11-22 · Time to restore last run: 18 min

## When to use it

The lab session ended (4-hour limit or overnight). EC2 hosts were stopped by Learner Lab and restarted by Start Lab. Terminal credentials are expired. RDS and Redshift were paused at end-of-day. `/predict` is not answering or returns 502.

## Before you start

- Open AWS Academy Learner Lab → Start Lab → wait for the dot to go green.
- Copy the new credentials block from "AWS Details → Show".
- You need: AWS CLI, `gh` CLI authenticated, `terraform` installed.

## Steps

One row per thing that was broken. Written while fixing it.

| # | Check (command) | Healthy looks like | If not: fix (command) | Took | Automated? |
| --- | --- | --- | --- | --- | --- |
| 1 | `aws sts get-caller-identity` | Returns account `590183860700` | Paste new credentials into `~/.aws/credentials` | 2 min | no — requires human to click Start Lab and copy credentials |
| 2 | `aws ec2 describe-instances --filters Name=tag:Project,Values=lab --query 'Reservations[].Instances[].State.Name'` | All `running` | Learner Lab starts hosts automatically; wait 2 min after Start Lab | 2 min | yes — Learner Lab does this |
| 3 | `aws rds describe-db-instances --db-instance-identifier lab --query 'DBInstances[0].DBInstanceStatus'` | `available` | `aws rds start-db-instance --db-instance-identifier lab` then wait ~3 min | 4 min | yes — `restore-boot.sh` on platform host boot |
| 4 | `aws redshift describe-clusters --cluster-identifier lab --query 'Clusters[0].ClusterStatus'` | `available` | `aws redshift resume-cluster --cluster-identifier lab` then wait ~4 min | 5 min | yes — `restore-boot.sh` on platform host boot |
| 5 | `ssh` via SSM into platform; `docker ps` | Dagster and MLflow containers running | They restart automatically (`restart: unless-stopped`) once RDS is up; wait ~1 min after RDS available | 1 min | yes — Docker restart policy |
| 6 | `curl http://<app_public_ip>/predict -X POST -H 'Content-Type: application/json' -d '{"pickup_zone_id":132,"dropoff_zone_id":230,"pickup_datetime":"2024-03-08T17:05:00"}'` | `{"alias":"champion"}` in response | Serving containers restart automatically; if not, `gh workflow run serving.yaml -R ShivanshTIwaRISS/mlops_project` | 2 min | yes — Docker restart policy |
| 7 | `gh workflow run status.yaml -R ShivanshTIwaRISS/mlops_project` | Workflow green, reports RDS and Redshift available | Fix whichever piece the status run reports as FAIL | 2 min | no — trigger is manual, human verifies |

## Done when

- `scripts/health.sh` exits 0.
- `curl -X POST http://<app_public_ip>/predict ...` returns `"alias":"champion"`.
- Status workflow is green and reports RDS `available`, Redshift `available`.

## What we automated, and what we left as a step

See [decisions/012-restore-automation.md](../decisions/012-restore-automation.md).

**Automated (runs on platform host boot via systemd):** RDS start, Redshift resume — both are safe to retry and have no side-effects if already running.

**Left as a manual step:** exporting new AWS credentials — the session token is personal, short-lived, and must be copied from the Learner Lab UI by the student. A machine cannot do this without storing a long-lived credential, which is a security violation in this lab.
