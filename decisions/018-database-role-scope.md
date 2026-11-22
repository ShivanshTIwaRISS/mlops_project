# 018: Dedicated read-only role scope for warehouse MCP tools

Stage: S7 · Date: 2026-11-22 · Author: student · Drafted by agent: yes

## Choice

Create a dedicated database user `lab_ro` configured with `PASSWORD DISABLE` (leveraging temporary IAM credentials through the Redshift Data API). Scope `lab_ro` permissions strictly to:
- `USAGE` on schema `marts`
- `SELECT` on all existing tables in `marts`
- `ALTER DEFAULT PRIVILEGES IN SCHEMA marts GRANT SELECT ON TABLES TO lab_ro;` so refreshed mart tables retain read access
- Explicitly revoke all access and creation privileges on `ingest`, `staging`, and `marts`.

## Rejected alternative

**Running tool queries as `labadmin`.** While convenient, using the administrative pipeline user would allow an injected prompt or tool bug to read raw uncurated trips in `ingest`, modify staging tables, or drop database objects.

## Why

1. **Least privilege defense-in-depth:** Even if an attacker achieves arbitrary query execution or exploits tool parameters, the database engine enforces that `lab_ro` can only read pre-aggregated historical metrics in `marts` and cannot insert, update, or read raw trip records.
2. **Surviving table refreshes:** Without `ALTER DEFAULT PRIVILEGES`, Dagster rebuilding `marts.zone_hour_stats` would drop and recreate the table, revoking `lab_ro`'s read access until manually regranted.
3. **No stored credentials:** Redshift Data API's `--db-user` authentication avoids storing static passwords in secrets, configs, or container environments.

## What would show this was wrong

If future assistant features require access to customer-specific trip records or real-time driver availability not stored in `marts`.
