#!/usr/bin/env bash
# S0: register a host as a self-hosted GitHub Actions runner (label: lab-<role>, from
# contracts/runtime.yaml), so the CD workflow can deploy with the host's instance profile.
set -euo pipefail
export AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1 AWS_PAGER=""

role=${1:?usage: scripts/register-runner.sh <role> (app|platform|llm)}
[[ "$role" =~ ^(app|platform|llm)$ ]] || { echo "role must be app, platform, or llm" >&2; exit 2; }

root="$(cd "$(dirname "$0")/.." && pwd)"
repo=$(gh repo view --json nameWithOwner -q .nameWithOwner) ||
  { echo "Could not determine GitHub repository with gh. Run gh auth login." >&2; exit 1; }

label="lab-${role}"
runners=$(gh api "repos/$repo/actions/runners" -q '.runners[] | "\(.name)=\(.status)"' 2>/dev/null || true)
if grep -q "${label}=online" <<<"$runners"; then
  echo "runner ${label} is already online"
  exit 0
fi

iid=$(terraform -chdir="$root/infra/live" output -raw "${role}_instance_id") ||
  { echo "Could not get ${role}_instance_id from terraform outputs" >&2; exit 1; }

echo "fetching GitHub runner registration token for $repo..."
token=$(gh api -X POST "repos/$repo/actions/runners/registration-token" -q .token) ||
  { echo "Failed to fetch runner registration token. Check gh authentication." >&2; exit 1; }

echo "waiting for $label ($iid) setup to complete..."
for _ in {1..30}; do
  status=$(aws ec2 describe-instances --instance-ids "$iid" --query 'Reservations[0].Instances[0].State.Name' --output text 2>/dev/null || echo unknown)
  if [[ "$status" == "running" ]]; then
    break
  fi
  sleep 5
done

RUNNER_VERSION="2.322.0"
script=$(cat <<EOF
set -euo pipefail

cd /opt/actions-runner
if [ ! -f ./config.sh ]; then
  curl -fsSL -o runner.tar.gz "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-arm64-${RUNNER_VERSION}.tar.gz"
  tar xzf runner.tar.gz
  rm -f runner.tar.gz
  chown -R runner:runner /opt/actions-runner
fi

./svc.sh stop 2>/dev/null || true
./svc.sh uninstall 2>/dev/null || true

su - runner -c "cd /opt/actions-runner && ./config.sh --url https://github.com/${repo} --token ${token} --name ${label} --labels ${label} --unattended --replace"
cd /opt/actions-runner
./svc.sh install runner
./svc.sh start
EOF
)

echo "sending registration command to $iid via SSM..."
params=$(jq -cn --arg s "$script" '{commands: [$s]}')
cmd_id=$(aws ssm send-command \
  --instance-ids "$iid" \
  --document-name "AWS-RunShellScript" \
  --parameters "$params" \
  --comment "Register runner $label" \
  --query "Command.CommandId" --output text)

echo "SSM command $cmd_id sent. Waiting for execution..."
status="Pending"
tries=0
while [[ "$status" =~ ^(Pending|InProgress|Delayed)$ ]]; do
  ((++tries <= 60)) || { echo "SSM timed out registering runner on $iid" >&2; exit 1; }
  sleep 3
  status=$(aws ssm get-command-invocation --command-id "$cmd_id" --instance-id "$iid" --query Status --output text 2>/dev/null || echo Pending)
done

if [[ "$status" != "Success" ]]; then
  echo "SSM command failed with status $status" >&2
  aws ssm get-command-invocation --command-id "$cmd_id" --instance-id "$iid" --query StandardErrorContent --output text >&2 || true
  exit 1
fi

echo "runner $label registered successfully"
