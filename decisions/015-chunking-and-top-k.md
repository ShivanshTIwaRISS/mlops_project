# 015: 250 max tokens, 50 token overlap, top-k 3

Stage: S6 · Date: 2026-11-22 · Author: student · Drafted by agent: yes

## Choice

Chunking configuration in `pipelines/src/labpipes/defs/rag.py` and retrieval configuration in `app/src/rideapp/assistant.py`:

- **max_tokens:** 250 tokens per chunk
- **overlap_tokens:** 50 tokens (~20% overlap)
- **top_k:** 3 chunks retrieved per question

## Rejected alternative

**Larger chunks (500+ tokens) and top-k 5.** On a CPU LLM host (m8g.large with Qwen3-4B-Instruct running under llama.cpp), prompt evaluation speed is ~13 tokens/second. Retrieving 5 chunks of 500 tokens (2,500 prompt tokens) would add over 180 seconds of prompt ingestion latency per rider request, causing frequent client timeouts on `/assist`.

**Smaller chunks (100 tokens) with top-k 1.** This would minimise latency (~10–15 s total), but single-paragraph chunks lose section context and cross-paragraph conditions (e.g. exceptions to surcharges or airport buffer rules that follow in the subsequent paragraph).

## Why

1. **Wiki characteristics:** The ops wiki pages are concise (short policy documents with markdown headers). At 250 tokens (~190 words), a chunk comfortably encapsulates an entire heading section along with the prepended page title and heading breadcrumb (`Page Title > Heading`).
2. **Overlap:** A 50-token overlap preserves continuity across paragraph breaks within longer sections without unnecessarily duplicating embeddings.
3. **Latency budget:** At top-k 3, retrieved context is ~750 tokens. Prompt evaluation takes ~45–55 seconds on CPU. When combined with llama.cpp's cached system prompt prefix, rider queries complete reliably within the 120–150 s client timeout (`contracts/assistant-openapi.yaml`).

## What would show this was wrong

If Langfuse traces reveal answers hallucinating because the relevant clause was cut off at a chunk boundary, increase overlap to 80 tokens. If riders frequently experience request timeouts on `/assist`, drop top-k to 2.
