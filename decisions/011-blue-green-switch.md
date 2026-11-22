# 011: What triggers the blue-green switch

Stage: S3 · Date: 2026-11-22 · Author: student · Drafted by agent: yes

## Choice

The blue-green switch is automated in the CD workflow: it flips traffic to the newly deployed colour immediately after two automated smoke tests pass on that colour:
1. `GET /version` returning 200 with the matching Git SHA.
2. `POST /predict` returning 200 with a valid numerical quote for a representative zone pair.

Rollback is also automated via workflow dispatch (`rollback: true`) with no re-build required.

## Rejected alternative

Requiring a human approval step before flipping the live traffic router to the newly deployed colour.

## Why

Application code undergoes extensive static analysis, linting, and unit testing in CI before reaching the CD phase. Adding a human in the loop for every application deploy slows down delivery without adding meaningful verification that automated smoke tests cannot perform better. Because the old colour remains running in parallel and rollback takes less than a second (a single Traefik route update), the blast radius of a failed deploy is minimal. Human approval is strictly reserved for promoting new model versions in MLflow (`production` environment).

## What would show this was wrong

If breaking bugs or performance regressions that pass basic single-prediction smoke tests (e.g. concurrency deadlocks, memory leaks under load, or subtle schema edge cases) reach live riders frequently, requiring repeated manual rollbacks.
