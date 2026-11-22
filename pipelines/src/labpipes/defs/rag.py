"""S6: the wiki RAG branch, in the `rag` database on RDS (pgvector), on a daily schedule.

- wiki_pages: the published pages from the ops wiki (resource `wiki`: labpipes/wiki.py). Store each
  page's ETag and send it next time: an unchanged page then costs a 304 and no body.
- wiki_chunks: split changed pages with labpipes.chunking.chunk_markdown (chunk size and overlap are
  decision 015) and store the chunks; use Chunk.content_hash as the id so unchanged text keeps it.
- wiki_embeddings: embed only the chunks that have no vector yet (resource `embed`: nomic-embed-text,
  768 dimensions) and store them as pgvector `vector(768)`, with an index (HNSW: decision 016).
- A blocking check that every chunk has a vector, and a schedule (and a job you can run by hand with
  scripts/dagster-run.sh) for the three.
"""

import dagster as dg

from labpipes.chunking import chunk_markdown
from labpipes.resources import LlmEmbed, RagStore, WikiApi

MAX_TOKENS = 250      # decision 015
OVERLAP_TOKENS = 50   # decision 015


@dg.asset(group_name="rag", compute_kind="postgres")
def wiki_pages(context: dg.AssetExecutionContext, wiki: WikiApi, rag: RagStore) -> dg.MaterializeResult:
    """Fetch published pages from the ops wiki using conditional GETs (ETags)."""
    client = wiki.client()
    pages_list = client.pages()

    with rag.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS rag;")
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS rag.pages (
                    id VARCHAR(64) PRIMARY KEY,
                    title TEXT NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    etag TEXT NOT NULL,
                    body TEXT NOT NULL
                );
                """
            )
            cur.execute("SELECT id, etag FROM rag.pages;")
            existing = {row[0]: row[1] for row in cur.fetchall()}

            fetched, cached = 0, 0
            live_ids = []
            for p in pages_list:
                live_ids.append(p.id)
                last_etag = existing.get(p.id)
                page = client.page(p.id, etag=last_etag)
                if page is None:
                    cached += 1
                else:
                    fetched += 1
                    cur.execute(
                        """
                        INSERT INTO rag.pages (id, title, updated_at, etag, body)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            title = EXCLUDED.title,
                            updated_at = EXCLUDED.updated_at,
                            etag = EXCLUDED.etag,
                            body = EXCLUDED.body;
                        """,
                        (page.id, page.title, page.updated_at, page.etag, page.body),
                    )

            if live_ids:
                cur.execute("DELETE FROM rag.pages WHERE id NOT IN %s;", (tuple(live_ids),))

        conn.commit()

    context.log.info(f"wiki_pages: fetched={fetched}, cached={cached}, total={len(pages_list)}")
    return dg.MaterializeResult(
        metadata={
            "fetched": dg.MetadataValue.int(fetched),
            "cached": dg.MetadataValue.int(cached),
            "total_pages": dg.MetadataValue.int(len(pages_list)),
        }
    )


@dg.asset(deps=[wiki_pages], group_name="rag", compute_kind="postgres")
def wiki_chunks(context: dg.AssetExecutionContext, rag: RagStore) -> dg.MaterializeResult:
    """Split wiki pages into content-hashed chunks with section-aware markdown splitting."""
    with rag.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS rag.chunks (
                    id VARCHAR(32) PRIMARY KEY,
                    page_id VARCHAR(64) NOT NULL REFERENCES rag.pages(id) ON DELETE CASCADE,
                    heading TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tokens INT NOT NULL,
                    embedding vector(768)
                );
                """
            )
            cur.execute("SELECT id, title, body FROM rag.pages;")
            pages = cur.fetchall()

            cur.execute("SELECT id FROM rag.chunks;")
            existing_chunks = {row[0] for row in cur.fetchall()}

            new_chunks = 0
            all_current_chunk_ids = []

            for page_id, title, body in pages:
                chunks = chunk_markdown(title, body, max_tokens=MAX_TOKENS, overlap_tokens=OVERLAP_TOKENS)
                page_chunk_ids = []
                for c in chunks:
                    cid = c.content_hash(page_id)
                    all_current_chunk_ids.append(cid)
                    page_chunk_ids.append(cid)
                    if cid not in existing_chunks:
                        new_chunks += 1
                        cur.execute(
                            """
                            INSERT INTO rag.chunks (id, page_id, heading, content, tokens)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (id) DO NOTHING;
                            """,
                            (cid, page_id, c.heading, c.text, c.tokens),
                        )
                if page_chunk_ids:
                    cur.execute(
                        "DELETE FROM rag.chunks WHERE page_id = %s AND id NOT IN %s;",
                        (page_id, tuple(page_chunk_ids)),
                    )

            cur.execute("SELECT count(*) FROM rag.chunks;")
            total_chunks = int(cur.fetchone()[0])

        conn.commit()

    context.log.info(f"wiki_chunks: total={total_chunks}, new_chunks={new_chunks}")
    return dg.MaterializeResult(
        metadata={
            "total_chunks": dg.MetadataValue.int(total_chunks),
            "new_chunks": dg.MetadataValue.int(new_chunks),
        }
    )


@dg.asset(deps=[wiki_chunks], group_name="rag", compute_kind="llm")
def wiki_embeddings(context: dg.AssetExecutionContext, embed: LlmEmbed, rag: RagStore) -> dg.MaterializeResult:
    """Generate 768-dim embeddings for all chunks that lack a vector, and ensure the HNSW index exists."""
    with rag.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, content FROM rag.chunks WHERE embedding IS NULL;")
            to_embed = cur.fetchall()

            embedded_count = len(to_embed)
            if to_embed:
                context.log.info(f"embedding {embedded_count} chunks in batches via LLM host...")
                chunk_ids = [row[0] for row in to_embed]
                texts = [row[1] for row in to_embed]
                vectors = embed.embed_documents(texts)

                for cid, vec in zip(chunk_ids, vectors, strict=True):
                    v_str = "[" + ",".join(f"{x:.7g}" for x in vec) + "]"
                    cur.execute(
                        "UPDATE rag.chunks SET embedding = %s::vector WHERE id = %s;",
                        (v_str, cid),
                    )

            # Build HNSW index on the vector column if it does not exist
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx
                ON rag.chunks USING hnsw (embedding vector_cosine_ops);
                """
            )
            cur.execute("SELECT count(*) FROM rag.chunks WHERE embedding IS NOT NULL;")
            total_embedded = int(cur.fetchone()[0])

        conn.commit()

    context.log.info(f"wiki_embeddings: embedded_count={embedded_count}, total_with_vector={total_embedded}")
    return dg.MaterializeResult(
        metadata={
            "embedded_chunks": dg.MetadataValue.int(embedded_count),
            "total_with_vector": dg.MetadataValue.int(total_embedded),
        }
    )


@dg.asset_check(asset=wiki_embeddings, blocking=True, description="Every wiki chunk has an embedding vector.")
def wiki_embeddings_complete(rag: RagStore) -> dg.AssetCheckResult:
    """Verify that no chunks are missing embeddings."""
    with rag.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM rag.chunks WHERE embedding IS NULL;")
            missing = int(cur.fetchone()[0])

    passed = missing == 0
    return dg.AssetCheckResult(
        passed=passed,
        severity=dg.AssetCheckSeverity.ERROR,
        description="All chunks embedded" if passed else f"{missing} chunks missing embedding",
        metadata={"missing_embeddings": dg.MetadataValue.int(missing)},
    )


ingest_wiki_job = dg.define_asset_job(
    "ingest_wiki",
    selection=dg.AssetSelection.assets(wiki_pages, wiki_chunks, wiki_embeddings)
    | dg.AssetSelection.checks(wiki_embeddings_complete),
    description="Daily sync of the ops wiki: conditional GETs, chunking, and embedding.",
)

wiki_daily_schedule = dg.ScheduleDefinition(
    job=ingest_wiki_job,
    cron_schedule="0 4 * * *",
    description="Ingest ops wiki daily at 04:00 UTC",
)
