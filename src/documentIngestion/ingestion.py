import asyncio
from fastapi import APIRouter
from documentIngestion.models.ingestionModels import ingestionRequest, ingestionResponse
from documentIngestion.contextual_retrieval import build_contextualized_document
from providers.llmProvider import build_mistral_client
from providers.embeddingModelProvider import embeddingModel
from db.neo4j import Neo4jClient
from db.neo4j.cypherQuerys import create_vector_index, save_chunk
from config import jina_api_key, neo4j_uri, neo4j_user, neo4j_password

ingestionRouter = APIRouter()

_INDEX_NAME = "chunk_vector_index"
_EMBEDDING_DIM = 512  # jina-embeddings-v2-small-en output dimension


@ingestionRouter.post("/ingest", response_model=ingestionResponse)
async def ingest_document(request: ingestionRequest):
    try:
        embedding_model = embeddingModel(
            api_key=jina_api_key,
            base_url="https://api.jina.ai/v1/embeddings",
            embeddingModel="jina-embeddings-v2-small-en",
            max_concurrency=10,
        )

        contextualized_document_chunk = await build_contextualized_document(
            file_path=request.file_path,
            client=await build_mistral_client(),
        )

        chunks = contextualized_document_chunk["chunks"]

        # Generate all embeddings concurrently
        embeddings = await asyncio.gather(*[
            embedding_model.generateEmebedding(chunk["contextualized_text"])
            for chunk in chunks
        ])

        # Initialise Neo4j connection and ensure the vector index exists
        neo4j_client = Neo4jClient(neo4j_uri, neo4j_user, neo4j_password)
        try:
            await create_vector_index(neo4j_client, _INDEX_NAME, _EMBEDDING_DIM)

            # Persist all chunks concurrently
            await asyncio.gather(*[
                save_chunk(neo4j_client, chunk, embedding)
                for chunk, embedding in zip(chunks, embeddings)
            ])
        finally:
            await neo4j_client.close()

        return ingestionResponse(status="success", message="Document ingested successfully")

    except Exception as e:
        return ingestionResponse(status="error", message=str(e))


