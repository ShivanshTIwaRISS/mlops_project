# 010: Model reload on alias change

Stage: S3 · Date: 2026-11-22 · Author: student · Drafted by agent: yes

## Choice

Use in-process hot reload (`POST /reload`) to swap the model weights when an MLflow alias moves. The serving container maintains the outgoing champion in memory to answer live rider requests until the new champion artifact is fully downloaded, deserialized, and warmed up.

## Rejected alternative

Restarting the serving container (e.g. `docker compose restart serving-champion`) whenever the alias changes, relying solely on start-up loading.

## Why

Restarting the container introduces an unavoidable window of downtime or degraded service: while the container restarts, pulls dependencies, and deserializes LightGBM model weights from S3/MLflow (which can take 5–15 seconds), requests fail with 503 or fall back to the coarse static median. With `POST /reload`, the previous model continues serving production traffic with zero downtime. The pointer swap in memory is atomic once the new model passes validation.

## What would show this was wrong

If repeated in-process reloads cause Python memory fragmentation or memory leaks over time (retaining old model objects in memory and causing an Out-Of-Memory kill on the EC2 host), we would need to switch to blue-green container swapping for the serving process itself.
