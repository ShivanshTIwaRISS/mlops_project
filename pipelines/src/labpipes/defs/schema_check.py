"""S1: the schema_contract check on trip_files.

Compare the landed file's Parquet footer (the DataBucket resource reads it) with
contracts/trips.schema.yaml, before raw_trips copies anything. contracts/platform.yaml says this check
is blocking.
"""

from dataclasses import asdict

import dagster as dg

from ..contracts import trips_schema
from ..partitions import trip_months
from ..resources import DataBucket


@dg.asset_check(
    asset="trip_files",
    partitions_def=trip_months,
    blocking=True,
    description="Parquet schema matches contracts/trips.schema.yaml in column names and storage types.",
)
def schema_contract(
    context: dg.AssetCheckExecutionContext, data_bucket: DataBucket
) -> dg.AssetCheckResult:
    month = context.partition_key
    footer = data_bucket.footer(month)
    expected = trips_schema()
    actual = footer.columns

    if len(actual) != len(expected):
        return dg.AssetCheckResult(
            passed=False,
            severity=dg.AssetCheckSeverity.ERROR,
            description=f"Column count mismatch: expected {len(expected)}, got {len(actual)}",
            metadata={"expected_count": len(expected), "actual_count": len(actual)},
        )

    mismatches = []
    for i, (exp, act) in enumerate(zip(expected, actual, strict=True)):
        if exp.name.lower() != act.name.lower():
            mismatches.append(f"Col {i} name mismatch: expected {exp.name}, got {act.name}")
        if exp.type != act.type:
            mismatches.append(f"Col {i} ({exp.name}) type mismatch: expected {exp.type}, got {act.type}")

    passed = len(mismatches) == 0
    return dg.AssetCheckResult(
        passed=passed,
        severity=dg.AssetCheckSeverity.ERROR,
        description="Parquet schema matches contract" if passed else f"{len(mismatches)} schema mismatches found",
        metadata={
            "mismatches": dg.MetadataValue.json(mismatches),
            "columns": dg.MetadataValue.json([asdict(c) for c in actual]),
        },
    )
