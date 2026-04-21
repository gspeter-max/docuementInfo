import asyncio
from typing import Any
from fastapi import APIRouter
import structlog

from src.documentIngestion.models.ingestionModels import ingestionRequest, ingestionResponse
from src.documentIngestion.contextual_retrieval import build_contextualized_document
from src.providers.llmProvider import build_mistral_client
from src.providers.embeddingModelProvider import embeddingModel
from src.db.neo4j import Neo4jClient
from src.db.neo4j.cypherQuerys import (
    create_vector_index, 
    save_chunk,
    save_document_node,
    save_entity_nodes_and_relationships
)
from src.documentIngestion.graphExtraction import extract_graph_data_from_chunk
from src.documentIngestion.entityResolution import (
    group_entities_by_normalized_name,
    find_fuzzy_merge_candidates,
    split_clear_cases_from_ambiguous_cases,
    resolve_ambiguous_entity_pairs,
)
from src.documentIngestion.graphPersistence import (
    rewrite_graph_results_to_canonical_entities,
    build_neo4j_graph_write_payload,
)
from src.config import jina_api_key, neo4j_uri, neo4j_user, neo4j_password

log = structlog.get_logger(__name__)

ingestionRouter = APIRouter()

_INDEX_NAME = "chunk_vector_index"
_EMBEDDING_DIM = 768  # jina-embeddings-v2-base-en output dimension


async def build_contextualized_chunk_embeddings(chunks: list[dict[str, Any]]) -> list[list[float]]:
    """Generates embeddings for all contextualized chunks concurrently."""
    embedding_model = embeddingModel(
        api_key=jina_api_key,
        base_url="https://api.jina.ai/v1/embeddings",
        embeddingModel="jina-embeddings-v2-base-en",
        max_concurrency=10,
    )
    if not chunks:
        return []
    texts = [chunk["contextualized_text"] for chunk in chunks]
    return await embedding_model.generate_embeddings_for_text_list(texts)


async def extract_chunk_graph_data_in_parallel(chunks: list[dict[str, Any]]) -> list[Any]:
    """Runs extraction over all chunks concurrently."""
    client = await build_mistral_client()
    return await asyncio.gather(*[
        extract_graph_data_from_chunk(llm_client=client, chunk=chunk)
        for chunk in chunks
    ])


async def resolve_entities_for_graph(raw_chunk_graph_results: list[Any]) -> dict[str, Any]:
    """Code-first funnel + focused LLM cleanup for entity names."""
    unique_names = set()
    for res in raw_chunk_graph_results:
        for e in res.entities:
            unique_names.add(e.entity_name)
        for r in res.relationships:
            unique_names.add(r.source_entity_name)
            unique_names.add(r.target_entity_name)
            
    if not unique_names:
        return {"canonical_name_by_raw_name": {}}

    grouped_names = group_entities_by_normalized_name(list(unique_names))
    canonical_map = {}
    for _, original_names in grouped_names.items():
        canonical_name = min(original_names, key=len)
        for name in original_names:
            canonical_map[name] = canonical_name
            
    # Then fuzzy merge
    unique_canonicals = list(set(canonical_map.values()))
    fuzzy_candidates = find_fuzzy_merge_candidates(unique_canonicals)
    # Fake scores for now
    same_pairs, ambiguous_pairs, _ = split_clear_cases_from_ambiguous_cases([(l, r, 0.75) for l, r in fuzzy_candidates])
    
    for l, r, _ in same_pairs:
        canonical_map[r] = canonical_map.get(l, l)

    client = await build_mistral_client()
    decisions = await resolve_ambiguous_entity_pairs(llm_client=client, ambiguous_pairs=ambiguous_pairs)
    
    for decision in decisions:
        if decision.should_merge:
            canonical_map[decision.left_name] = decision.canonical_name
            canonical_map[decision.right_name] = decision.canonical_name

    return {"canonical_name_by_raw_name": canonical_map}


async def persist_document_graph(
    doc: dict[str, Any],
    embeddings: list[list[float]],
    graph_write_payload: dict[str, Any] # We pass the whole payload now
) -> None:
    neo4j_client = Neo4jClient(neo4j_uri, neo4j_user, neo4j_password)
    try:
        await create_vector_index(neo4j_client, _INDEX_NAME, _EMBEDDING_DIM)
        
        await save_document_node(
            neo4j_client, 
            doc["document_id"], 
            doc.get("source_file", "")
        )

        chunks = doc["chunks"]
        chunk_to_ids_map = graph_write_payload.get("chunk_to_entity_ids", {})

        # Save all chunks at once, each with its own list of name codes
        await asyncio.gather(*[
            save_chunk(
                neo4j_client, 
                chunk, 
                embedding, 
                entity_ids=chunk_to_ids_map.get(chunk["chunk_id"], [])
            )
            for chunk, embedding in zip(chunks, embeddings)
        ])
        
        # Save the graph nodes and connections
        await save_entity_nodes_and_relationships(neo4j_client, graph_write_payload)

    finally:
        await neo4j_client.close()


def build_ingestion_summary_response(contextualized_document: dict[str, Any], canonical_graph_payload: Any) -> dict[str, int | str]:
    return {
        "status": "success",
        "message": "Document ingested successfully",
        "raw_entity_count": len(canonical_graph_payload.entities),
        "canonical_entity_count": len(set(e["canonical_name"] for e in canonical_graph_payload.entities)),
        "relationship_count": len(canonical_graph_payload.relationships),
    }


async def ingest_document_graph(file_path: str) -> dict[str, int | str]:
    """Core document ingestion graph processing pipeline."""
    doc = await build_contextualized_document(file_path=file_path, client=await build_mistral_client())
    embeddings = await build_contextualized_chunk_embeddings(doc["chunks"])
    raw_results = await extract_chunk_graph_data_in_parallel(doc["chunks"])
    resolution_result = await resolve_entities_for_graph(raw_results)
    
    canonical_payload = rewrite_graph_results_to_canonical_entities(
        raw_results,
        resolution_result["canonical_name_by_raw_name"],
    )
    
    # Send the finished payload to be saved
    graph_write_payload = build_neo4j_graph_write_payload(
        doc["document_id"],
        canonical_payload.entities,
        canonical_payload.relationships,
    )
    
    await persist_document_graph(
        doc, 
        embeddings, 
        graph_write_payload
    )
    
    return build_ingestion_summary_response(doc, canonical_payload)


@ingestionRouter.post("/ingest", response_model=ingestionResponse)
async def ingest_document(request: ingestionRequest):
    """This gets the request from the web when someone wants to process a document, and hands it over to the big boss function to do the work."""
    try:
        summary = await ingest_document_graph(request.file_path)
        return ingestionResponse(**summary)
    except Exception as e:
        log.error("Ingestion failed", error=str(e), exc_info=True)
        return ingestionResponse(status="error", message=str(e))
