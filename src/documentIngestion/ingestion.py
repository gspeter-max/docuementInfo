import asyncio
from fastapi import APIRouter
from src.documentIngestion.models.ingestionModels import ingestionRequest, ingestionResponse
from src.documentIngestion.contextual_retrieval import (
    build_mistral_client,
    build_contextualized_document
)
from src.providers.embeddingModelProvider import embeddingModel
from config import jina_api_key

ingestionRouter = APIRouter()

@ingestionRouter.post("/ingest", response_model=ingestionResponse)
async def ingest_document(request: ingestionRequest):
    try:
        embedding_model = embeddingModel(
            api_key=jina_api_key,
            base_url="https://api.jina.ai/v1/embeddings",
            embeddingModel="jina-embeddings-v2-small-en",
            max_concurrency=10
        )

        contextualized_document_chunk = await build_contextualized_document(
            file_path=request.file_path,
            client=await build_mistral_client(),
        )

        tasks = []
        for chunk in contextualized_document_chunk["chunks"]:
            tasks.append(embedding_model.generateEmebedding(chunk["contextualized_text"]))

        embeddings = await asyncio.gather(*tasks)

        return ingestionResponse(status="success", message="Document ingested successfully")
    except Exception as e:
        return ingestionResponse(status="error", message=str(e))
