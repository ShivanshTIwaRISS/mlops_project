# 001: runner credentials

Stage: S0 · Date: 2026-11-21 · Author: student · Drafted by agent: yes

## Choice

Authenticate the self-hosted GitHub Actions runner on the EC2 host using the EC2 instance profile (`LabInstanceProfile`) via IMDSv2.

## Rejected alternative

Storing AWS session credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`) as GitHub repository secrets.

## Why

AWS Academy Learner Lab session credentials expire every 4 hours, which would require constant manual token rotations in GitHub Secrets. Using `LabInstanceProfile` provides automatic credential retrieval and rotation without storing long-lived or short-lived credentials in GitHub. Since fork-PR workflows are configured to require repository maintainer approval before executing, the self-hosted runner and its attached instance profile are protected from unauthorized public PR code execution.

## What would show this was wrong

If jobs on the runner require AWS IAM permissions outside what `LabRole` provides, or if deployment jobs must run on GitHub-hosted runners where EC2 instance metadata is unreachable.

