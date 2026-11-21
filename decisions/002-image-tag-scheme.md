# 002: image tag scheme

Stage: S0 · Date: 2026-11-21 · Author: student · Drafted by agent: yes

## Choice

Tag container images built by CI with the git commit short SHA (`sha-<short-sha>`).

## Rejected alternative

Semantic versioning (`vMAJOR.MINOR.PATCH`) or a mutable `latest` tag.

## Why

The git commit SHA provides deterministic, immutable provenance linking every running container in production directly to an exact commit in git. Rollbacks are straightforward and unambiguous (re-deploying the tag of the previous good commit). Semantic versioning adds manual release overhead during rapid lab iterations, while `latest` is non-deterministic and creates docker caching inconsistencies.

## What would show this was wrong

If external consumers or downstream services require human-readable semantic versioning contracts (e.g. SemVer guarantees for public API consumers).

