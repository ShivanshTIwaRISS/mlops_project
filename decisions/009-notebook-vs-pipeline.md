# 009: What stays in the notebook vs the pipeline

Stage: S2 · Date: 2026-11-21 · Author: student · Drafted by agent: yes

## Choice

Exploratory analysis, hyperparameter experimentation, and model comparison (v1 baseline vs v2 LightGBM vs static median) stay in the notebook. The pipeline encodes the fixed best parameters, the UNLOAD logic, MLflow logging, the evaluation gate, and the challenger alias assignment.

## Rejected alternative

Running hyperparameter search inside the Dagster pipeline (e.g. with Optuna), and promoting the best trial automatically.

## Why

The notebook is the right place for decisions that require human judgment: choosing which features to trust, examining data distributions, and deciding that LightGBM with 300 rounds and num_leaves=127 is good enough to ship. Once decided, those choices belong in version-controlled pipeline code — reproducible, testable, and auditable. Embedding hyperparameter search in the pipeline would make every training run expensive, non-deterministic, and harder to reason about in a code review. The grader and a future colleague reading the pipeline should see one clear set of parameters, not a search space.

## What would show this was wrong

If the best notebook parameters degrade significantly on new months' data (e.g. MAE rises by >10% on 2024-05), it would signal the parameters need to be revisited through another notebook experiment rather than being frozen.

