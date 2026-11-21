# 006: data quality checks gating (blocking vs warning)

Stage: S1 · Date: 2026-11-21 · Author: student · Drafted by agent: yes

## Choice

Enforce strict blocking on structural schema mismatches (`schema_contract` on `trip_files`) and fatal data corruptions (null timestamps, invalid location IDs outside 1..263), while emitting warnings for non-critical statistical anomalies (minor price outliers, plausible fare extremes).

## Rejected alternative

Making every data quality check blocking, or alternatively making all quality checks non-blocking warnings.

## Why

Parquet `COPY` in Redshift maps columns positionally; any schema shift (column missing or reordered) causes silent data corruption or load failure, so schema contract checks must strictly block before loading. Fatal corruptions in mandatory identifier columns break relational integrity in `marts.zone_hour_stats`. However, real-world taxi data naturally contains edge cases (e.g. disputed fares, high tips). Blocking the entire monthly pipeline for minor statistical outliers would halt production operations unnecessarily.

## What would show this was wrong

If corrupt or poisoned data that degrades downstream ML model training slips through as non-blocking warnings and reaches the champion model.

