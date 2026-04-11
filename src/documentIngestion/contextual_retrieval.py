"""
Contextual retrieval pipeline.

This module parses a document, chunks the full text, generates a short
retrieval-oriented summary for each chunk, and returns contextualized chunks.
It does not embed text or write vectors.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import asyncio
from openai import AsyncOpenAI
from src.config import mistral_api_key
from src.documentIngestion.chunking import chunk_document
from src.documentIngestion.parseDocument import get_all_pages_text, parse_document

MISTRAL_BASE_URL = "https://api.mistral.ai/v1"
DEFAULT_MODEL = "mistral-small-latest"


async def build_mistral_client(
    api_key: str | None = None,
    base_url: str = MISTRAL_BASE_URL,
) -> AsyncOpenAI:
    resolved_api_key = (api_key or mistral_api_key or "").strip()
    if not resolved_api_key:
        raise EnvironmentError(
            "MISTRAL_API_KEY is not set. "
            "Set it in your .env file, expose it from src.config, or pass it explicitly."
        )

    return AsyncOpenAI(api_key=resolved_api_key, base_url=base_url)


async def  build_context_messages(full_document_text: str, chunk: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You write concise retrieval context for document chunks. "
                "Your job is to explain where this chunk fits in the larger document."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Document id: {chunk['document_id']}\n"
                f"Chunk index: {chunk['chunk_index']}\n"
                f"Chunk token count: {chunk['token_count']}\n\n"
                f"Full document text:\n{full_document_text}\n\n"
                f"Chunk text:\n{chunk['text']}\n\n"
                "Write 1 to 3 short sentences that help retrieval. "
                "Mention the section, topic, or document role of this chunk. "
                "Do not summarize the chunk alone. Return plain text only."
            ),
        },
    ]


async def generate_chunk_context(
    *,
    client: AsyncOpenAI,
    full_document_text: str,
    chunk: dict[str, Any],
    model: str = DEFAULT_MODEL,
    max_tokens: int = 120,
) -> dict[str, Any]:
    messages = await build_context_messages(full_document_text, chunk)
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.0,
        max_tokens=max_tokens,
    )
    if inspect.isawaitable(response):
        response = await response
    message = response.choices[0].message
    context = (message.content or "").strip()
    contextualized_text = f"{context}\n\n{chunk['text']}"
    return {
        **chunk,
        "context": context,
        "contextualized_text": contextualized_text,
        "model": model,
    }


async def build_contextualized_document(
    *,
    file_path: str,
    client: AsyncOpenAI,
    model: str = DEFAULT_MODEL,
    max_concurrency = 10
) -> dict[str, Any]:
    parsed = parse_document(file_path)
    full_document_text = get_all_pages_text(parsed)
    document_id = Path(file_path).name
    chunks = chunk_document(full_document_text, document_id=document_id)

    sem = asyncio.Semaphore(max_concurrency)
    async def _run_one(chunk : dict[str, Any]):
        async with sem:
            return await generate_chunk_context(
                client=client,
                full_document_text=full_document_text,
                chunk=chunk,
                model=model,
            )

    tasks = [_run_one(chunk) for chunk in chunks]
    contextualized_chunks = await asyncio.gather(*tasks)

    return {
        "document_id": document_id,
        "source_file": file_path,
        "full_document_text": full_document_text,
        "chunks": contextualized_chunks,
        "chunk_count": len(contextualized_chunks),
        "model": model,
    }
