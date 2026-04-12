import asyncio
from fastapi import APIRouter
from documentIngestion.models.ingestionModels import ingestionRequest, ingestionResponse
from documentIngestion.contextual_retrieval import build_contextualized_document
from providers.llmProvider import build_mistral_client
from providers.embeddingModelProvider import embeddingModel
from db.neo4j import Neo4jClient
from db.neo4j.cypherQuerys import create_vector_index, save_chunk
from config import jina_api_key, neo4j_uri, neo4j_user, neo4j_password
import structlog

log = structlog.get_logger(__name__)

ingestionRouter = APIRouter()

_INDEX_NAME = "chunk_vector_index"
_EMBEDDING_DIM = 768  # jina-embeddings-v2-base-en output dimension


@ingestionRouter.post("/ingest", response_model=ingestionResponse)
async def ingest_document(request: ingestionRequest):
    try:
        embedding_model = embeddingModel(
            api_key=jina_api_key,
            base_url="https://api.jina.ai/v1/embeddings",
            embeddingModel="jina-embeddings-v2-base-en",
            max_concurrency=10,
        )
        log.info("Starting contextualized document builder", file_path=request.file_path)

        contextualized_document_chunk = await build_contextualized_document(
            file_path=request.file_path,
            client=await build_mistral_client(),
        )

        chunks = contextualized_document_chunk["chunks"]
        log.info("Contextualized document built successfully", chunk_count=len(chunks))

        # Generate all embeddings concurrently
        log.info("Generating embeddings", chunk_count=len(chunks))
        embeddings = await asyncio.gather(*[
            embedding_model.generateEmebedding(chunk["contextualized_text"])
            for chunk in chunks
        ])
        log.info("Embeddings generated successfully")

        # Initialise Neo4j connection and ensure the vector index exists
        neo4j_client = Neo4jClient(neo4j_uri, neo4j_user, neo4j_password)
        try:
            await create_vector_index(neo4j_client, _INDEX_NAME, _EMBEDDING_DIM)

            # Persist all chunks concurrently
            await asyncio.gather(*[
                save_chunk(neo4j_client, chunk, embedding)
                for chunk, embedding in zip(chunks, embeddings)
            ])

            log.info("Document ingested successfully", file_path=request.file_path)
            results = await neo4j_client.execute_query("MATCH (c:Chunk) RETURN count(c) as total")
            log.info("Chunks stored in Neo4j", count=results[0]["total"])
        finally:
            await neo4j_client.close()
        return ingestionResponse(status="success", message="Document ingested successfully")

    except Exception as e:
        log.error("Ingestion failed", error=str(e), exc_info=True)
        return ingestionResponse(status="error", message=str(e))


