#!/usr/bin/env bash
# restore-boot.sh — run once on platform host boot via lab-restore.service
# Resumes RDS and Redshift if they are stopped/paused.
# Uses EC2 instance profile credentials (LabRole) — no stored keys.
set -euo pipefail

REGION="us-east-1"
RDS_ID="lab"
REDSHIFT_ID="lab"

echo "[restore] $(date -u +%Y-%m-%dT%H:%M:%SZ) starting"

# --- RDS ---
rds_status=$(aws rds describe-db-instances \
  --db-instance-identifier "$RDS_ID" \
  --region "$REGION" \
  --query 'DBInstances[0].DBInstanceStatus' \
  --output text 2>/dev/null || echo "unknown")

echo "[restore] RDS status: $rds_status"

if [ "$rds_status" = "stopped" ]; then
  echo "[restore] starting RDS $RDS_ID ..."
  aws rds start-db-instance --db-instance-identifier "$RDS_ID" --region "$REGION"
elif [ "$rds_status" = "available" ]; then
  echo "[restore] RDS already available, skipping"
else
  echo "[restore] RDS in state '$rds_status', skipping start"
fi

# --- Redshift ---
rs_status=$(aws redshift describe-clusters \
  --cluster-identifier "$REDSHIFT_ID" \
  --region "$REGION" \
  --query 'Clusters[0].ClusterStatus' \
  --output text 2>/dev/null || echo "unknown")

echo "[restore] Redshift status: $rs_status"

if [ "$rs_status" = "paused" ]; then
  echo "[restore] resuming Redshift $REDSHIFT_ID ..."
  aws redshift resume-cluster --cluster-identifier "$REDSHIFT_ID" --region "$REGION"
elif [ "$rs_status" = "available" ]; then
  echo "[restore] Redshift already available, skipping"
else
  echo "[restore] Redshift in state '$rs_status', skipping resume"
fi

echo "[restore] $(date -u +%Y-%m-%dT%H:%M:%SZ) done"
