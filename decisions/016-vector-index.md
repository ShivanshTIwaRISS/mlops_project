# 016: HNSW index with cosine distance for pgvector

Stage: S6 · Date: 2026-11-22 · Author: student · Drafted by agent: yes

## Choice

Use **HNSW** (Hierarchical Navigable Small World) index over cosine distance (`vector_cosine_ops`) for the `embedding` column in `rag.chunks`:

```sql
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx
ON rag.chunks USING hnsw (embedding vector_cosine_ops);
```

## Rejected alternative

**IVFFlat** (`USING ivfflat (embedding vector_cosine_ops)`). IVFFlat partitions vector space into Voronoi cells via k-means clustering. It requires a large training dataset to build effective centroids (typically lists >= sqrt(rows)) and requires periodic index rebuilding (`REINDEX`) as new pages or chunks are added, otherwise recall sharply deteriorates.

## Why

1. **Incremental build without pre-training:** Our ops wiki ingest pipeline runs daily, adding or modifying only changed chunks. HNSW supports dynamic, incremental insertions without needing to rebuild or re-cluster the index.
2. **High recall out of the box:** For small to medium vector collections (< 100,000 vectors), HNSW provides superior recall (>95%) with low query latency compared to IVFFlat without requiring manual tuning of `lists` or `probes`.
3. **Memory footprint is acceptable:** Although HNSW builds larger in-memory graph structures than IVFFlat, our corpus consists of hundreds of chunks (16 wiki pages yielding ~100 chunks), consuming negligible RAM on RDS (`db.t4g.micro` / `medium`).

## What would show this was wrong

If the chunk collection scales beyond several million vectors where index build memory exceeds RDS RAM limits and index creation times become prohibitive, revisit IVFFlat or partition the table.
