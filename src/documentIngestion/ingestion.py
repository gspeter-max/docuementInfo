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
    all_raw_names = []
    for res in raw_chunk_graph_results:
        all_raw_names.extend([e.entity_name for e in res.entities])
        all_raw_names.extend([r.source_entity_name for r in res.relationships])
        all_raw_names.extend([r.target_entity_name for r in res.relationships])
        
    unique_raw_names = list(set(all_raw_names))
    if not unique_raw_names:
        return {"canonical_name_by_raw_name": {}}

    grouped_names = group_entities_by_normalized_name(unique_raw_names)
    canonical_name_by_raw_name = {}
    for normalized_name, original_names in grouped_names.items():
        canonical_name = sorted(original_names, key=len)[0]
        for name in original_names:
            canonical_name_by_raw_name[name] = canonical_name
            
    # Then fuzzy merge
    unique_canonicals = list(set(canonical_name_by_raw_name.values()))
    fuzzy_candidates = find_fuzzy_merge_candidates(unique_canonicals)
    
    # Fake scores for now
    pairs_with_scores = [(l, r, 0.75) for l, r in fuzzy_candidates]
    same_entity_pairs, ambiguous_pairs, different_entity_pairs = split_clear_cases_from_ambiguous_cases(pairs_with_scores)
    
    for l, r, _ in same_entity_pairs:
        canonical_name_by_raw_name[r] = canonical_name_by_raw_name.get(l, l)

    client = await build_mistral_client()
    decisions = await resolve_ambiguous_entity_pairs(llm_client=client, ambiguous_pairs=ambiguous_pairs)
    
    for decision in decisions:
        if decision.should_merge:
            canonical_name_by_raw_name[decision.left_name] = decision.canonical_name
            canonical_name_by_raw_name[decision.right_name] = decision.canonical_name

    return {"canonical_name_by_raw_name": canonical_name_by_raw_name}


async def persist_document_graph(
    contextualized_document: dict[str, Any],
    contextualized_chunk_embeddings: list[list[float]],
    canonical_graph_payload: Any
) -> None:
    """Writes chunks to Neo4j, then writes the canonical graph extraction payload."""
    neo4j_client = Neo4jClient(neo4j_uri, neo4j_user, neo4j_password)
    try:
        await create_vector_index(neo4j_client, _INDEX_NAME, _EMBEDDING_DIM)
        
        await save_document_node(
            neo4j_client, 
            contextualized_document["document_id"], 
            contextualized_document.get("source_file", "")
        )

        chunks = contextualized_document["chunks"]
        await asyncio.gather(*[
            save_chunk(neo4j_client, chunk, embedding)
            for chunk, embedding in zip(chunks, contextualized_chunk_embeddings)
        ])
        
        graph_write_payload = build_neo4j_graph_write_payload(
            contextualized_document["document_id"],
            canonical_graph_payload.entities,
            canonical_graph_payload.relationships,
        )
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
    """This is the big boss function. It takes one document, breaks it into pieces, finds names and connections in each piece, cleans up the names so there are no duplicates, and saves everything into the database."""
    contextualized_document = await build_contextualized_document(file_path=file_path, client=await build_mistral_client())
    contextualized_chunk_embeddings = await build_contextualized_chunk_embeddings(contextualized_document["chunks"])
    raw_chunk_graph_results = await extract_chunk_graph_data_in_parallel(contextualized_document["chunks"])
    canonical_resolution_result = await resolve_entities_for_graph(raw_chunk_graph_results)
    
    canonical_graph_payload = rewrite_graph_results_to_canonical_entities(
        raw_chunk_graph_results,
        canonical_resolution_result["canonical_name_by_raw_name"],
    )
    
    await persist_document_graph(
        contextualized_document, 
        contextualized_chunk_embeddings, 
        canonical_graph_payload
    )
    
    return build_ingestion_summary_response(contextualized_document, canonical_graph_payload)


@ingestionRouter.post("/ingest", response_model=ingestionResponse)
async def ingest_document(request: ingestionRequest):
    """This gets the request from the web when someone wants to process a document, and hands it over to the big boss function to do the work."""
    try:
        summary = await ingest_document_graph(request.file_path)
        return ingestionResponse(**summary)
    except Exception as e:
        log.error("Ingestion failed", error=str(e), exc_info=True)
        return ingestionResponse(status="error", message=str(e))
