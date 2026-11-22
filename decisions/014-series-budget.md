# 014: drop go/process metrics, cAdvisor id/image labels, and Traefik internals

Stage: S5 · Date: 2026-11-22 · Author: student · Drafted by agent: yes

## Choice

Three-tier relabelling in `observability/alloy/budget.alloy`:

| Tier | Keep | Drop |
|------|------|------|
| **host** | `node_cpu_*`, `node_memory_*`, `node_filesystem_*`, `node_load*`, `node_network_*`, `node_uname_info` | all other node_* (schedstat, sockstat, timex, …) |
| **containers** | `container_cpu_usage_seconds_total`, `container_memory_working_set_bytes` | all other cAdvisor metrics; drop `id` and `image` label values |
| **services** | all `lab_*` metrics, `traefik_service_*` | `go_*`, `process_*`, `traefik_config_*`, `traefik_entrypoint_*`, `traefik_router_*`, `traefik_middleware_*` |

Expected active series after three CD deploys: **~1 500–2 500 per host** (3 000–5 000 total for app + platform), leaving **~5 000 headroom** for the LLM host in S6 and canary label variants in S8.

## Rejected alternative

**Drop all cAdvisor metrics entirely.** This would save ~200–400 series per host but remove the "Container memory (working set)" and "Host CPU busy" dashboard panels, breaking visibility into OOM kills and runaway containers. These are the two signals most likely to explain a serving outage, so the cost is higher than the saving.

## Why

**go_* and process_***: Each service (app, serving-champion, serving-challenger, Dagster, MLflow, Traefik) emits ~40–80 Go runtime metrics. Across five services on two hosts that is ~400–800 series with no dashboard panel or SLO rule. Pure noise.

**cAdvisor `id` and `image` labels**: `id` is the container ID hash (`/docker/abc123…`) and `image` is the full image digest (`sha256:…`). Both change on every `docker compose up --force-recreate`. Without the labeldrop, each CD deploy mints a fresh set of series that Grafana Cloud counts as new active series for two hours (staleness window). After ten deploys, the cAdvisor series count has tripled. Dropping those two labels makes the series stable across deploys.

**Traefik internal metrics** (config, router, middleware, entrypoint): Not in `contracts/metrics.yaml`, not on any dashboard panel, not used in S8's canary. Only `traefik_service_*` is needed for per-service request counts and latency.

## What would show this was wrong

If `observability/alloy-stats.sh` reports active series approaching 8 000 after S6's LLM host joins, revisit the host tier — `node_schedstat_*` and `node_softnet_*` can be dropped next. If a serving incident happens that the dropped metrics would have explained (e.g., Go GC pause spike), add `go_gc_duration_seconds` back.
