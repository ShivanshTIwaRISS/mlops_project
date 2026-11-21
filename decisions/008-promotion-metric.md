# 008: Promotion metric and margin

Stage: S2 · Date: 2026-11-21 · Author: student · Drafted by agent: yes

## Choice

A new version becomes `challenger` only if its holdout MAE is at least 2% better than the champion's (new_mae < champion_mae × 0.98) **and** its p95 single-row latency is below 50 ms.

## Rejected alternative

Promoting any version that beats the champion by any margin (new_mae < champion_mae), ignoring latency.

## Why

A margin-free gate accepts noise. If a re-train on identical data produces an MAE 0.1% lower due to random seed variation, it would trigger a promotion and deploy a new model for no meaningful gain. The 2% threshold filters noise while still catching real improvements. The latency guard (50 ms p95) exists because serving evaluates one row at a time per request: a model that's more accurate but 3× slower would breach SLA and hurt user experience. Both conditions must hold — accuracy without latency is not safe to deploy.

## What would show this was wrong

If the 2% bar is too strict and genuinely better models (confirmed on additional test sets) are blocked from becoming challengers, the threshold should be revisited. If p95 latency for single-row inference consistently sits at 20–30 ms, the 50 ms budget is generous and could be tightened to 40 ms in a future decision.

