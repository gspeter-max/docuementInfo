from db.neo4j import Neo4jClient
from typing import Any


# ─── Index Setup ──────────────────────────────────────────────────────────────

async def create_vector_index(client: Neo4jClient, index_name: str, dimension: int) -> None:
    """
    Run once at startup.
    Creates a cosine-similarity vector index on the Chunk.embedding property.
    `dimension` must match the embedding model output
    (e.g. 512 for jina-embeddings-v2-small-en).
    The IF NOT EXISTS guard makes it safe to call on every startup.
    """
    query = f"""
    CREATE VECTOR INDEX {index_name} IF NOT EXISTS
    FOR (c:Chunk) ON (c.embedding)
    OPTIONS {{
        indexConfig: {{
            `vector.dimensions`: {dimension},
            `vector.similarity_function`: 'cosine'
        }}
    }}
    """
    await client.execute_query(query)


# ─── Write ────────────────────────────────────────────────────────────────────

async def save_chunk(
    client: Neo4jClient,
    chunk: dict[str, Any],
    embedding: list[float],
) -> None:
    """
    Upserts a single Chunk node with its contextualized text and embedding vector.
    MERGE on chunk_id avoids duplicate nodes when the same document is re-ingested.

    Expected keys in `chunk`:
        chunk_index  – unique identifier for this chunk
        text         – raw chunk text
        context      – LLM-generated contextual prefix
        document_id  – parent document identifier
    """
    query = """
    MERGE (c:Chunk {chunk_id: $chunk_id})
    SET c.text        = $text,
        c.context     = $context,
        c.document_id = $document_id,
        c.embedding   = $embedding
    """
    await client.execute_query(query, {
        "chunk_id":    chunk["chunk_index"],
        "text":        chunk["text"],
        "context":     chunk["context"],
        "document_id": chunk["document_id"],
        "embedding":   embedding,
    })


# ─── Read ─────────────────────────────────────────────────────────────────────

async def retrieve_similar_chunks(
    client: Neo4jClient,
    index_name: str,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """
    Runs a vector similarity search against `index_name`.

    Returns a list of dicts, each containing:
        full_context  – context prepended to chunk text, ready for LLM prompt
        score         – cosine similarity (0–1, higher = more similar)
        chunk_id      – for traceability
        document_id   – for traceability
    """
    query = """
    CALL db.index.vector.queryNodes($index_name, $top_k, $embedding)
    YIELD node, score
    RETURN
        node.context + '\n\n' + node.text AS full_context,
        score,
        node.chunk_id    AS chunk_id,
        node.document_id AS document_id
    ORDER BY score DESC
    """
    return await client.execute_query(query, {
        "index_name": index_name,
        "top_k":      top_k,
        "embedding":  query_embedding,
    })