# 004: COPY vs Redshift Spectrum

Stage: S1 · Date: 2026-11-21 · Author: student · Drafted by agent: yes

## Choice

Ingest and store monthly taxi trip data natively into Redshift using the `COPY` command rather than querying external Parquet files directly with Redshift Spectrum.

## Rejected alternative

Querying landed files in-place on Amazon S3 using Redshift Spectrum external tables.

## Why

While Redshift Spectrum avoids loading data into the warehouse and saves local disk storage, native tables populated via `COPY` offer significantly faster analytical performance, columnar compression encoding, and local sort key indexing. In our MLOps pipeline, mart aggregations (`zone_hour_stats`) and downstream feature engineering require repeated reads and percentile calculations, which perform much more efficiently on native storage. Furthermore, `COPY` provides clean boundary isolation where bad or malformed monthly data can be validated and quarantined in staging before ever touching production marts.

## What would show this was wrong

If data volume scales to dozens of terabytes exceeding cluster storage capacity, or if raw data is accessed so infrequently that storage costs significantly outweigh query performance benefits.

