# 007: Training window

Stage: S2 · Date: 2026-11-21 · Author: student · Drafted by agent: yes

## Choice

Train on 2024-01, 2024-02, and 2024-03; evaluate on 2024-04 as the holdout month.

## Rejected alternative

A random 80/20 split of all four months' rows mixed together.

## Why

A chronological split avoids target leakage from future time-based patterns. If January and April rows are mixed and 20% of April rows end up in the training set, the model sees April's post-holiday traffic patterns during training but is then evaluated on the same distribution, overstating real-world accuracy. The holdout must be a full month the model has never seen — 2024-04 provides a clean, contiguous out-of-time test. Three months of training data (≈9 million trips) gives LightGBM enough zone-pair coverage to learn meaningful embeddings for the categorical zone IDs.

## What would show this was wrong

If seasonal drift is severe (e.g. January and March patterns are radically different from April due to events, construction, or policy changes), the model would underperform in deployment despite passing the holdout gate. Adding more months — once available — and comparing rolling-window evaluations would surface this.

