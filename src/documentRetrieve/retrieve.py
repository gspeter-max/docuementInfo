"""
Main retrieval pipeline and FastAPI router for the /query endpoint.
"""
from typing import Any
import structlog
from fastapi import APIRouter

from config import neo4j_uri, neo4j_user, neo4j_password, jina_api_key
from db.neo4j import Neo4jClient
from db.neo4j.cypherQuerys import retrieve_similar_chunks
from providers.embeddingModelProvider import embeddingModel
from providers.llmProvider import build_mistral_client, DEFAULT_MODEL
from providers.voyageRerankProvider import rerank_documents

from documentRetrieve.models import QueryRequest, QueryResponse
from documentRetrieve.router import classify_intent
from documentRetrieve.grader import grade_chunks
from documentRetrieve.graphAgent import gather_graph_facts

log = structlog.get_logger()
retrieveRouter = APIRouter()

# Name of the Neo4j vector index for chunks (should match ingestion)
CHUNK_VECTOR_INDEX = "chunk_embedding_index"


def extract_entity_ids_from_chunks(chunks: list[dict[str, Any]]) -> list[str]:
    """Extracts a deduplicated list of entity_ids from retrieved chunk dictionaries."""
    entity_ids = set()
    for chunk in chunks:
        ids = chunk.get("entity_ids")
        if isinstance(ids, list):
            entity_ids.update(ids)
    return list(entity_ids)


async def generate_final_answer(query: str, context_texts: list[str]) -> str:
    """Uses Mistral to generate the final answer based on the reranked context."""
    if not context_texts:
        return "I could not find relevant information to answer your query."

    context_block = "\n\n---\n\n".join(context_texts)
    prompt = f"""
You are a helpful and precise assistant. Answer the user's query using ONLY the provided context.
If the context does not contain the answer, say so clearly. Do not hallucinate external facts.

CONTEXT:
{context_block}
"""

    try:
        client = await build_mistral_client()
        response = await client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": query},
            ],
            temperature=0.0,
        )
        return response.choices[0].message.content or "No answer generated."
    except Exception as e:
        log.error("Failed to generate final answer", error=str(e))
        return "Error generating answer from LLM."


async def handle_query(request: QueryRequest) -> QueryResponse:
    """
    Executes the Hybrid Adaptive RAG pipeline.
    """
    query = request.query
    intent = await classify_intent(query)
    log.info("Query intent classified", intent=intent, query=query)

    # 1. Embed Query
    embedder = embeddingModel(api_key=jina_api_key)
    query_embedding = await embedder.generateEmebedding(query)

    client = Neo4jClient(neo4j_uri, neo4j_user, neo4j_password)
    
    used_graph_search = False
    reason_for_graph_search = ""
    context_to_rerank = []

    try:
        # 2. Vector Search (always done as baseline)
        raw_chunks = await retrieve_similar_chunks(
            client=client,
            index_name=CHUNK_VECTOR_INDEX,
            query_embedding=query_embedding,
            top_k=request.top_k,
        )
        
        vector_texts = [c["full_context"] for c in raw_chunks]
        log.info("Vector search complete", num_chunks=len(vector_texts))

        answer = ""

        if intent == "complex":
            # Complex: always go to graph
            used_graph_search = True
            entities = extract_entity_ids_from_chunks(raw_chunks)
            graph_facts = await gather_graph_facts(client, entities)
            
            context_to_rerank = vector_texts.copy()
            if graph_facts:
                context_to_rerank.append(graph_facts)
                
            # Rerank and generate answer
            log.info("Reranking context", num_items=len(context_to_rerank))
            final_context = await rerank_documents(query=query, documents=context_to_rerank, top_k=request.top_k_rerank)
            log.info("Generating final answer")
            answer = await generate_final_answer(query, final_context)

        else:
            # Simple: evaluate vector chunks and attempt to generate answer
            grader_result = await grade_chunks(query, vector_texts)
            
            if grader_result.sufficient:
                # Fast path! The grader already generated the answer.
                answer = grader_result.answer
                final_context = vector_texts
            else:
                # Recovery path: escalate to graph
                used_graph_search = True
                reason_for_graph_search = grader_result.reason
                log.info("Escalating simple query to graph", reason=reason_for_graph_search)
                
                entities = extract_entity_ids_from_chunks(raw_chunks)
                graph_facts = await gather_graph_facts(client, entities)
                
                context_to_rerank = vector_texts.copy()
                if graph_facts:
                    context_to_rerank.append(graph_facts)
                
                # Rerank and generate answer
                log.info("Reranking context", num_items=len(context_to_rerank))
                final_context = await rerank_documents(query=query, documents=context_to_rerank, top_k=request.top_k_rerank)
                log.info("Generating final answer")
                answer = await generate_final_answer(query, final_context)

        return QueryResponse(
            answer=answer,
            intent=intent,
            used_graph_search=used_graph_search,
            reason_for_graph_search=reason_for_graph_search,
            context_used=final_context,
        )

    finally:
        await client.close()


@retrieveRouter.post("/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest):
    """
    POST endpoint to run the Hybrid Adaptive RAG pipeline.
    """
    return await handle_query(request)
