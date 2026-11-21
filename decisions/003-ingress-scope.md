# 003: ingress scope

Stage: S0 · Date: 2026-11-21 · Author: student · Drafted by agent: yes

## Choice

Restrict ingress on port 80 (Traefik) to explicit CIDR blocks: the student's current laptop IP (`115.244.141.202/32`) and the instructor/grader IP block specified in `terraform.tfvars`.

## Rejected alternative

Opening ingress on port 80 to the public internet (`0.0.0.0/0`).

## Why

Adheres to least privilege and shields the EC2 host from automated internet vulnerability scanners, bot traffic, and unauthenticated requests during development. Port 80 serves Traefik which routes to the app, so restricting access to known IPs reduces attack surface.

## What would show this was wrong

If the student frequently switches Wi-Fi networks / mobile hotspots during the workshop and gets locked out until updating `terraform.tfvars` and reapplying.

