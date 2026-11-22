#!/usr/bin/env python3
"""Promote a model version to the champion alias in MLflow (S3).

Verifies that the target version carries required pipeline evaluation tags before promoting.
Records the outgoing champion version if one exists.
"""

from __future__ import annotations

import os
import sys

from mlflow import MlflowClient

MODEL_NAME = "trip-duration"
REQUIRED_TAGS = ["mae_min", "p95_latency_ms", "training_window", "holdout_month"]


def main() -> int:
    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")
    if not tracking_uri:
        print("MLFLOW_TRACKING_URI not set", file=sys.stderr)
        return 1

    client = MlflowClient(tracking_uri=tracking_uri)

    target = os.environ.get("TARGET_VERSION", "").strip()
    if not target:
        try:
            challenger = client.get_model_version_by_alias(MODEL_NAME, "challenger")
            target = challenger.version
            print(f"Targeting challenger version: {target}")
        except Exception as e:
            print(f"Failed to resolve challenger alias: {e}", file=sys.stderr)
            return 1
    else:
        print(f"Targeting requested version: {target}")

    try:
        mv = client.get_model_version(MODEL_NAME, target)
    except Exception as e:
        print(f"Failed to fetch model version {target}: {e}", file=sys.stderr)
        return 1

    tags = mv.tags or {}
    missing = [t for t in REQUIRED_TAGS if t not in tags]
    if missing:
        print(
            f"Cannot promote version {target}: missing pipeline evaluation tags {missing}. "
            "Only versions evaluated by the pipeline can become champion.",
            file=sys.stderr,
        )
        return 1

    mae = tags.get("mae_min", "unknown")
    lat = tags.get("p95_latency_ms", "unknown")
    print(f"Version {target} verified with pipeline metrics: MAE={mae}m, p95={lat}ms")

    try:
        outgoing = client.get_model_version_by_alias(MODEL_NAME, "champion")
        print(f"Outgoing champion was version {outgoing.version}")
    except Exception:
        print("No outgoing champion (first promotion)")

    client.set_registered_model_alias(MODEL_NAME, "champion", target)
    print(f"Successfully promoted version {target} to champion!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
