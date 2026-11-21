"""S2: the feature_contract check on trip_features.

Compares staging.trip_features columns against contracts/features.yaml:
- All input columns are present with correct Redshift types
- Label column is present
- No forbidden post-trip columns (target leakage) exist in the table

contracts/mlflow.yaml says this check blocks: a column mismatch stops training before it starts.
"""

import dagster as dg

from ..contracts import features_contract
from ..partitions import trip_months
from ..resources import RedshiftData

# Redshift type mapping for features.yaml types
_REDSHIFT_TYPES: dict[str, str] = {
    "integer": "integer",
    "smallint": "smallint",
    "double precision": "double precision",
    "char(7)": "char",
}


@dg.asset_check(
    asset="trip_features",
    partitions_def=trip_months,
    blocking=True,
    description="Columns of staging.trip_features match contracts/features.yaml: inputs, label, no forbidden columns.",
)
def feature_contract(
    context: dg.AssetCheckExecutionContext, redshift: RedshiftData
) -> dg.AssetCheckResult:
    month = context.partition_key
    contract = features_contract()

    # Query the actual columns from Redshift information_schema
    rows = redshift.query(
        "select column_name, data_type from information_schema.columns "
        "where table_schema = 'staging' and table_name = 'trip_features' "
        "order by ordinal_position"
    )
    actual_cols = {r["column_name"].lower(): r["data_type"].lower() for r in rows}

    mismatches: list[str] = []

    # Check all required input columns exist
    for inp in contract["inputs"]:
        name = inp["name"].lower()
        expected_type = inp["type"].lower()
        if name not in actual_cols:
            mismatches.append(f"Missing input column: {name}")
        else:
            # Normalize expected type for comparison
            expected_base = _REDSHIFT_TYPES.get(expected_type, expected_type)
            actual_base = actual_cols[name]
            if expected_base not in actual_base and actual_base not in expected_base:
                mismatches.append(
                    f"Column {name}: expected type {expected_type}, got {actual_cols[name]}"
                )

    # Check label column exists
    label = contract["label"]["name"].lower()
    if label not in actual_cols:
        mismatches.append(f"Missing label column: {label}")

    # Check NO forbidden (post-trip) column exists (leakage guard)
    for forbidden in contract.get("forbidden", []):
        if forbidden.lower() in actual_cols:
            mismatches.append(f"Forbidden post-trip column present: {forbidden}")

    # Spot-check the month partition has rows
    row_count = redshift.scalar(
        f"select count(*) from staging.trip_features where trip_month = '{month}'"
    )
    if int(row_count or 0) == 0:
        mismatches.append(f"No rows found for partition {month}")

    passed = len(mismatches) == 0
    return dg.AssetCheckResult(
        passed=passed,
        severity=dg.AssetCheckSeverity.ERROR,
        description=(
            "Feature table matches contract"
            if passed
            else f"{len(mismatches)} feature contract violation(s)"
        ),
        metadata={
            "mismatches": dg.MetadataValue.json(mismatches),
            "actual_columns": dg.MetadataValue.json(list(actual_cols.keys())),
            "row_count": dg.MetadataValue.int(int(row_count or 0)),
        },
    )
