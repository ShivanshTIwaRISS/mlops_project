"""S1: the S3 sensor (and the job it starts).

Watch trips/ in the data bucket (DataBucket.trip_files). When a month's file appears or changes, add
the month to the trip_months partitions and request a run that goes from trip_files to zone_hour_stats.
"""

import json

import dagster as dg

from ..partitions import trip_months
from ..resources import DataBucket

ingest_job = dg.define_asset_job(
    "ingest_month",
    selection=dg.AssetSelection.assets("trip_files", "raw_trips", "stg_trips", "zone_hour_stats"),
    description="Ingest one month from S3 into Redshift and rebuild zone_hour_stats mart.",
)


@dg.sensor(
    job=ingest_job,
    minimum_interval_seconds=60,
    name="trip_files_sensor",
    description="Watches trips/ in the data bucket and launches an ingestion run for each new/changed month.",
)
def trip_files_sensor(context: dg.SensorEvaluationContext, data_bucket: DataBucket):
    cursor = json.loads(context.cursor or "{}")
    files = data_bucket.trip_files()
    new_or_changed = []
    new_partitions = []

    for f in files:
        if f.month not in cursor or cursor[f.month] != f.etag:
            new_or_changed.append(f)
            if f.month not in cursor:
                new_partitions.append(f.month)
            cursor[f.month] = f.etag

    if not new_or_changed:
        return dg.SkipReason("No new or modified trip files found in data bucket.")

    run_requests = [
        dg.RunRequest(partition_key=f.month, run_key=f"{f.month}-{f.etag}")
        for f in new_or_changed
    ]

    dynamic_partitions_requests = (
        [trip_months.build_add_request(sorted(new_partitions))]
        if new_partitions
        else []
    )

    return dg.SensorResult(
        run_requests=run_requests,
        dynamic_partitions_requests=dynamic_partitions_requests,
        cursor=json.dumps(cursor),
    )
