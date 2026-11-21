"""S1: the raw_trips asset.

One partition per month (partitions.trip_months), depending on trip_files. COPY the month's file into
Redshift with the LabRole attached to the cluster (`iam_role default`), so that re-running a month never
duplicates its rows.
"""

import dagster as dg

from ..contracts import redshift_columns, trips_schema
from ..partitions import check_month, source_file, trip_months
from ..resources import DataBucket, RedshiftData


@dg.asset(partitions_def=trip_months, deps=["trip_files"], group_name="ingest", kinds={"redshift"}, pool="redshift")
def raw_trips(
    context: dg.AssetExecutionContext, redshift: RedshiftData, data_bucket: DataBucket
) -> dg.MaterializeResult:
    month = check_month(context.partition_key)
    file_name = source_file(month)
    uri = data_bucket.trip_uri(month)
    cols_ddl = redshift_columns(trips_schema())
    col_names = ", ".join(c.name.lower() for c in trips_schema())

    redshift.execute(
        "create schema if not exists ingest",
        f"create table if not exists ingest.raw_trips (source_file varchar(64) not null, {cols_ddl}) sortkey (tpep_pickup_datetime)",
        f"delete from ingest.raw_trips where source_file = '{file_name}'",
        f"create temp table stage_raw_trips ({cols_ddl})",
        f"copy stage_raw_trips from '{uri}' iam_role default format as parquet",
        f"insert into ingest.raw_trips (source_file, {col_names}) select '{file_name}', {col_names} from stage_raw_trips",
        "drop table stage_raw_trips",
    )

    rows = redshift.scalar(f"select count(*) from ingest.raw_trips where source_file = '{file_name}'")
    return dg.MaterializeResult(
        metadata={
            "rows": dg.MetadataValue.int(int(rows)),
            "source_file": file_name,
            "source_uri": uri,
        }
    )
