"""S2: training_set, trained_model, eval_report, the challenger gate and the challenger asset.

Training window: 2024-01..2024-03 (train) | 2024-04 (holdout).
Promotion gate:  new_mae < champion_mae * 0.98  AND  p95_latency_ms < 50 ms.
No person sets the challenger alias: only this asset, behind the blocking gate.
"""

import os
import pathlib

import dagster as dg
import mlflow
import mlflow.pyfunc

import tripmodel
from tripmodel import BaselineModel, LightGBMModel, evaluate, model_signature

from ..contracts import mlflow_contract
from ..resources import ArtifactBucket, MlflowTracking, RedshiftData

# ── constants ──────────────────────────────────────────────────────────────────
TRAIN_MONTHS = ["2024-01", "2024-02", "2024-03"]
HOLDOUT_MONTH = "2024-04"
TRAINING_WINDOW = f"{TRAIN_MONTHS[0]}..{TRAIN_MONTHS[-1]}"

# Promotion thresholds (Decision 2: MAE ≥2% improvement AND latency < 50 ms)
MAE_IMPROVEMENT_THRESHOLD = 0.98   # new_mae must be < champion_mae * this
LATENCY_BUDGET_MS = 50.0


# ── 1. training_set ────────────────────────────────────────────────────────────

@dg.asset(group_name="model", kinds={"s3", "redshift"}, pool="redshift",
          description="UNLOAD the training window and holdout month from Redshift to the artifact bucket.")
def training_set(redshift: RedshiftData, artifacts: ArtifactBucket) -> dg.MaterializeResult:
    """UNLOAD trip_features for train months and holdout to S3 as Parquet."""
    months_sql = ", ".join(f"''{m}''" for m in TRAIN_MONTHS)
    holdout_sql = f"''{HOLDOUT_MONTH}''"

    train_prefix = "training/train/"
    holdout_prefix = "training/holdout/"
    dist_prefix = "training/distances/"

    train_uri = artifacts.uri(train_prefix)
    holdout_uri = artifacts.uri(holdout_prefix)
    dist_uri = artifacts.uri(dist_prefix)

    redshift.execute(
        f"unload ('select pickup_zone_id, dropoff_zone_id, pickup_hour, pickup_dow, duration_min "
        f"from staging.trip_features where trip_month in ({months_sql})') "
        f"to '{train_uri}' iam_role default format as parquet allowoverwrite",
    )
    redshift.execute(
        f"unload ('select pickup_zone_id, dropoff_zone_id, pickup_hour, pickup_dow, duration_min "
        f"from staging.trip_features where trip_month = ({holdout_sql})') "
        f"to '{holdout_uri}' iam_role default format as parquet allowoverwrite",
    )
    # Zone-pair distance lookup: median trip_distance from the training window (from stg_trips)
    redshift.execute(
        f"unload ('select pickup_zone_id, dropoff_zone_id, median(trip_distance) as est_distance_miles "
        f"from staging.stg_trips where trip_month in ({months_sql}) "
        f"and pickup_zone_id between 1 and 263 and dropoff_zone_id between 1 and 263 "
        f"group by pickup_zone_id, dropoff_zone_id') "
        f"to '{dist_uri}' iam_role default format as parquet allowoverwrite",
    )

    train_rows = redshift.scalar(
        f"select count(*) from staging.trip_features where trip_month in ({months_sql})"
    )
    holdout_rows = redshift.scalar(
        f"select count(*) from staging.trip_features where trip_month = ({holdout_sql})"
    )
    return dg.MaterializeResult(metadata={
        "training_window": TRAINING_WINDOW,
        "holdout_month": HOLDOUT_MONTH,
        "train_rows": dg.MetadataValue.int(int(train_rows or 0)),
        "holdout_rows": dg.MetadataValue.int(int(holdout_rows or 0)),
        "train_uri": train_uri,
        "holdout_uri": holdout_uri,
    })


# ── 2. trained_model ────────────────────────────────────────────────────────────

@dg.asset(deps=[training_set], group_name="model", kinds={"mlflow"},
          description="Fit LightGBMModel on the training window, log and register in MLflow.")
def trained_model(artifacts: ArtifactBucket, tracking: MlflowTracking) -> dg.MaterializeResult:
    """Fit v2 LightGBM, log to MLflow, register version with all required tags."""
    contract = mlflow_contract()
    client = tracking.client()

    train = artifacts.read_parquet("training/train/")
    distances = artifacts.read_parquet("training/distances/")

    model = LightGBMModel().fit(train, distances)

    git_sha = os.environ.get("GITHUB_SHA", "local")[:7]
    tripmodel_dir = str(pathlib.Path(tripmodel.__file__).parent)

    with mlflow.start_run() as run:
        run_id = run.info.run_id
        mlflow.log_params({
            "training_window": TRAINING_WINDOW,
            "holdout_month": HOLDOUT_MONTH,
            "num_rounds": 300,
            "features_version": str(contract.get("version", 1)),
        })
        info = mlflow.pyfunc.log_model(
            name="model",
            python_model=model,
            signature=model_signature(),
            code_paths=[tripmodel_dir],
            registered_model_name=contract["registered_model"],
        )
        version = info.registered_model_version

    # Tag the registered version with everything contracts/mlflow.yaml requires
    version_tags = {
        "training_window": TRAINING_WINDOW,
        "holdout_month": HOLDOUT_MONTH,
        "features_version": str(contract.get("version", 1)),
        "git_sha": git_sha,
    }
    for tag_name, tag_val in version_tags.items():
        client.set_model_version_tag(contract["registered_model"], version, tag_name, tag_val)

    return dg.MaterializeResult(metadata={
        "run_id": run_id,
        "version": dg.MetadataValue.int(int(version)),
        "registered_model": contract["registered_model"],
        "training_window": TRAINING_WINDOW,
        "holdout_month": HOLDOUT_MONTH,
    })


# ── 3. eval_report ─────────────────────────────────────────────────────────────

@dg.asset(deps=[trained_model], group_name="model", kinds={"mlflow"},
          description="Evaluate the new version and champion on the same holdout; log metrics.")
def eval_report(artifacts: ArtifactBucket, tracking: MlflowTracking, redshift: RedshiftData) -> dg.MaterializeResult:
    """Compare new version vs champion (or v1 baseline) on the holdout month."""
    contract = mlflow_contract()
    client = tracking.client()

    holdout = artifacts.read_parquet("training/holdout/")
    distances = artifacts.read_parquet("training/distances/")
    train = artifacts.read_parquet("training/train/")

    # Latest registered version
    versions = client.search_model_versions(f"name='{contract['registered_model']}'")
    latest = max(versions, key=lambda v: int(v.version))
    new_version = latest.version

    new_model = mlflow.pyfunc.load_model(f"models:/{contract['registered_model']}/{new_version}")

    # Borough lookup for slice evaluation
    borough_rows = redshift.query("select location_id, borough from ingest.taxi_zones")
    boroughs = {int(r["location_id"]): r["borough"] for r in borough_rows if r["borough"]}

    new_metrics = evaluate(new_model.predict, holdout, boroughs)

    # Compare against champion, or v1 baseline if no champion exists yet
    try:
        champ_model = mlflow.pyfunc.load_model(f"models:/{contract['registered_model']}@champion")
        champ_metrics = evaluate(champ_model.predict, holdout, boroughs)
        champion_mae = champ_metrics["mae_min"]
    except Exception:
        v1 = BaselineModel().fit(train, distances)
        champ_metrics = evaluate(lambda df: v1.predict(None, df), holdout, boroughs)
        champion_mae = champ_metrics["mae_min"]

    all_metrics = {**new_metrics, "champion_mae_min": champion_mae}

    # Log metrics on the most recent run
    experiment = mlflow.get_experiment_by_name(contract["experiment"])
    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        order_by=["attributes.start_time DESC"],
        max_results=1,
    )
    if runs:
        with mlflow.start_run(run_id=runs[0].info.run_id):
            mlflow.log_metrics(all_metrics)

    # Tag version with key metrics for the gate check
    for tag in ["mae_min", "p95_latency_ms", "champion_mae_min"]:
        if tag in all_metrics:
            client.set_model_version_tag(
                contract["registered_model"], new_version, tag, str(round(all_metrics[tag], 4))
            )

    return dg.MaterializeResult(metadata={
        "new_version": dg.MetadataValue.int(int(new_version)),
        "mae_min": dg.MetadataValue.float(round(new_metrics["mae_min"], 4)),
        "champion_mae_min": dg.MetadataValue.float(round(champion_mae, 4)),
        "p95_latency_ms": dg.MetadataValue.float(round(new_metrics["p95_latency_ms"], 4)),
        "mae_improvement_pct": dg.MetadataValue.float(
            round((1 - new_metrics["mae_min"] / champion_mae) * 100, 2)
        ),
    })


# ── 4. beats_champion (blocking check on eval_report) ─────────────────────────

@dg.asset_check(
    asset=eval_report,
    blocking=True,
    description=(
        "New version beats champion by ≥2% MAE AND p95 latency < 50 ms. "
        "Blocks challenger alias if either condition fails."
    ),
)
def beats_champion(tracking: MlflowTracking) -> dg.AssetCheckResult:
    """Gate: new version must improve MAE by ≥2% AND stay under 50 ms p95 latency."""
    contract = mlflow_contract()
    client = tracking.client()

    versions = client.search_model_versions(f"name='{contract['registered_model']}'")
    latest = max(versions, key=lambda v: int(v.version))

    tags = {t.key: t.value for t in latest.tags}
    new_mae = float(tags.get("mae_min", "inf"))
    champion_mae = float(tags.get("champion_mae_min", "inf"))
    p95_latency = float(tags.get("p95_latency_ms", "inf"))

    mae_ok = new_mae < champion_mae * MAE_IMPROVEMENT_THRESHOLD
    latency_ok = p95_latency < LATENCY_BUDGET_MS
    passed = mae_ok and latency_ok

    reasons = []
    if not mae_ok:
        improvement_pct = (1 - new_mae / champion_mae) * 100
        reasons.append(
            f"MAE improvement {improvement_pct:.2f}% < required 2% "
            f"(new={new_mae:.4f}, champion={champion_mae:.4f})"
        )
    if not latency_ok:
        reasons.append(f"p95 latency {p95_latency:.1f} ms >= budget {LATENCY_BUDGET_MS} ms")

    return dg.AssetCheckResult(
        passed=passed,
        severity=dg.AssetCheckSeverity.ERROR,
        description=(
            f"Model v{latest.version}: MAE {new_mae:.4f} vs champion {champion_mae:.4f}, "
            f"latency {p95_latency:.1f} ms — gate {'PASSED' if passed else 'FAILED'}"
        ),
        metadata={
            "new_version": dg.MetadataValue.int(int(latest.version)),
            "new_mae_min": dg.MetadataValue.float(new_mae),
            "champion_mae_min": dg.MetadataValue.float(champion_mae),
            "p95_latency_ms": dg.MetadataValue.float(p95_latency),
            "mae_threshold": dg.MetadataValue.float(MAE_IMPROVEMENT_THRESHOLD),
            "latency_budget_ms": dg.MetadataValue.float(LATENCY_BUDGET_MS),
        },
    )


# ── 5. challenger ──────────────────────────────────────────────────────────────

@dg.asset(
    deps=[eval_report],
    group_name="model",
    kinds={"mlflow"},
    description="Set the 'challenger' alias on the version that passed the gate. Never moves 'champion'.",
)
def challenger(tracking: MlflowTracking) -> dg.MaterializeResult:
    """Set challenger alias on the latest registered version."""
    contract = mlflow_contract()
    client = tracking.client()

    versions = client.search_model_versions(f"name='{contract['registered_model']}'")
    latest = max(versions, key=lambda v: int(v.version))

    client.set_registered_model_alias(
        contract["registered_model"], "challenger", latest.version
    )

    tags = {t.key: t.value for t in latest.tags}
    return dg.MaterializeResult(metadata={
        "version": dg.MetadataValue.int(int(latest.version)),
        "alias": "challenger",
        "mae_min": dg.MetadataValue.float(float(tags.get("mae_min", 0))),
        "p95_latency_ms": dg.MetadataValue.float(float(tags.get("p95_latency_ms", 0))),
        "training_window": tags.get("training_window", TRAINING_WINDOW),
    })


# ── 6. train_model job ─────────────────────────────────────────────────────────

train_model_job = dg.define_asset_job(
    "train_model",
    selection=dg.AssetSelection.assets(
        training_set, trained_model, eval_report, challenger
    ),
    description="Full training pipeline: UNLOAD -> fit -> evaluate -> gate -> set challenger alias.",
)
