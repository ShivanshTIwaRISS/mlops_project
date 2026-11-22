# 013: predict-availability at 99%, predict-latency (p95) at 95% within 500 ms

Stage: S5 · Date: 2026-11-22 · Author: student · Drafted by agent: yes

## Choice

Two SLOs for the ride app's `/predict` endpoint:

| SLO | SLI metric | Objective | Error budget |
|-----|-----------|-----------|--------------|
| predict-availability | fraction of non-5xx responses | 99% | ~7.3 h/month |
| predict-latency | fraction of requests completing < 500 ms | 95% | ~36 h/month |

## Rejected alternative

**99.9% availability** (43 min/month error budget). This is the typical production target for a customer-facing API, and it would be aspirational here. Rejected because the Learner Lab stops EC2 hosts at the 4-hour session boundary — a single overnight gap consumes the entire monthly budget. Setting 99.9% would mean the SLO is in permanent breach and the alert would fire continuously, making it useless as a signal.

## Why

**Availability at 99%:** The 7.3 h/month budget covers lab session gaps (up to 8 h overnight), blue-green deploys (~30 s each × ~20 deploys/week ≈ 10 min/month), and model reload windows. The error budget is not tight enough to prevent toil — it's tight enough to page on a container crash (which consumes budget at 100× the burn rate and fires within 5 minutes via the fast-burn alert).

**Latency at 95% / 500 ms:** The model itself takes ~3.5 ms (S2 eval). Traefik routing, JSON serialisation, and the app's Redshift distance lookup add overhead. The serving contract targets p95 < 50 ms for the serving layer; adding the app overhead, 500 ms is a generous but meaningful ceiling. 95% (not 99%) is chosen because cold model loads on container start take 2–3 s and are part of normal operations; 99% at 500 ms would fire on every restart.

## What would show this was wrong

If the availability SLO is in breach even on healthy days (Learner Lab restarted but service recovered fine), the objective is too strict for the lab's operational reality — lower to 95% or use an alerting window that excludes known maintenance.

If the latency SLO never fires even when the model is visibly slow in Grafana, the 500 ms threshold is too generous — tighten to 200 ms p95.
