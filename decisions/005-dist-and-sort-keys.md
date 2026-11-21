# 005: distribution and sort keys for trip tables

Stage: S1 · Date: 2026-11-21 · Author: student · Drafted by agent: yes

## Choice

Sort trip tables (`ingest.raw_trips` and `staging.stg_trips`) by pickup timestamp (`tpep_pickup_datetime` / `pickup_at`), and use `AUTO` / `EVEN` distribution style.

## Rejected alternative

Distributing by `PULocationID` (Key distribution) or sorting by `fare_amount` / `total_amount`.

## Why

Trip data is fundamentally partitioned and queried by time (monthly ingestion, time-window aggregations, hour/day-of-week feature extraction). Sorting on pickup timestamp allows Redshift's query engine to leverage zone maps to skip irrelevant data blocks during range scans. Because `marts.zone_hour_stats` aggregates across all zones and hours, an even distribution prevents data skew across cluster slices, ensuring uniform query processing times.

## What would show this was wrong

If queries become predominantly large joins between `stg_trips` and dimensional tables on `PULocationID` where network redistribution overhead dominates query execution time.

