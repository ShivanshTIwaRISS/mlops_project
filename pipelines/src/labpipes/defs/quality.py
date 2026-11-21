"""S1: data-quality checks on stg_trips (nulls, ranges, duplicates, row counts)."""

import dagster as dg

from ..partitions import check_month, trip_months
from ..resources import RedshiftData


@dg.asset_check(
    asset="stg_trips",
    partitions_def=trip_months,
    blocking=False,
    description="Check for nonpositive duration, durations > 3h, null passengers, and unknown zones.",
)
def stg_trips_quality(context: dg.AssetCheckExecutionContext, redshift: RedshiftData) -> dg.AssetCheckResult:
    month = check_month(context.partition_key)
    sql = f"""
    select count(*) as rows,
           count(case when duration_min <= 0 then 1 end) as nonpositive_duration,
           count(case when duration_min > 180 then 1 end) as over_3h,
           count(case when passenger_count is null then 1 end) as null_passengers,
           count(case when pickup_zone_id not between 1 and 263 or dropoff_zone_id not between 1 and 263 then 1 end) as unknown_zone
    from staging.stg_trips
    where trip_month = '{month}'
    """
    res = redshift.query(sql)[0]
    total = int(res["rows"])
    bad_durations = int(res.get("nonpositive_duration", 0))
    unknown_zones = int(res.get("unknown_zone", 0))

    passed = total > 0 and (bad_durations / total < 0.05)
    return dg.AssetCheckResult(
        passed=passed,
        severity=dg.AssetCheckSeverity.WARN,
        description=f"{total} rows checked; {bad_durations} non-positive durations, {unknown_zones} unknown zones",
        metadata={
            "total_rows": dg.MetadataValue.int(total),
            "nonpositive_duration": dg.MetadataValue.int(bad_durations),
            "unknown_zone": dg.MetadataValue.int(unknown_zones),
        },
    )
