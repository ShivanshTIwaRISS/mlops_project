# 017: Read-only tool granularity and confirmation boundary

Stage: S7 · Date: 2026-11-22 · Author: student · Drafted by agent: yes

## Choice

Expose three granular, purpose-built read-only MCP tools (`get_model_info`, `predict_duration`, `query_zone_stats`) with strict schema validation. Allow autonomous execution for read queries without human confirmation, while establishing that any future write tools (e.g. fare adjustments, booking rides) must require explicit human confirmation.

## Rejected alternative

**Generic SQL query tool.** Allowing the LLM to write arbitrary SQL queries against Redshift would open severe SQL injection vulnerabilities, resource exhaustion risks (e.g. expensive full-table joins), and schema reconnaissance.

**Human-in-the-loop confirmation for read tools.** Requiring rider or operator confirmation before calling `predict_duration` or `query_zone_stats` would break the autonomous real-time user experience of the conversational assistant for zero-side-effect operations.

## Why

1. **Deterministic schema validation:** Purpose-built tools validate TLC zone names against standard taxi zone identifiers with typo correction and enforce strict parameter bounds (`hour` 0..23, valid day of week).
2. **Zero side-effects:** Read-only model inference and aggregated historical stats queries do not mutate database state, charge payment methods, or impact physical fleet operations.
3. **Safety boundary:** If the assistant is expanded to support transactional write operations (booking, refunding, dispatch), human confirmation becomes mandatory to protect against indirect prompt injections and hallucinated actions.

## What would show this was wrong

If prompt injections manipulate tool arguments to bypass application-level business constraints or generate heavy analytical queries that degrade warehouse performance for other users.
