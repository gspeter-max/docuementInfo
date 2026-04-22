"""
Voyage AI reranker provider.

Calls https://api.voyageai.com/v1/rerank (rerank-2 model),
sorts results by relevance_score descending, returns top_k strings.

Uses run_in_executor so the synchronous requests.post call
does not block the asyncio event loop.
"""
import asyncio
from typing import Optional

import requests

from config import voyage_api_key

VOYAGE_RERANK_URL = "https://api.voyageai.com/v1/rerank"
VOYAGE_RERANK_MODEL = "rerank-2"


def _sync_rerank(
    query: str,
    documents: list[str],
    top_k: int,
    api_key: str,
) -> list[str]:
    """
    Synchronous HTTP call to Voyage /v1/rerank.
    Sorts by relevance_score descending and returns the top_k document strings.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": VOYAGE_RERANK_MODEL,
        "query": query,
        "documents": documents,
        "top_k": top_k,
    }
    response = requests.post(VOYAGE_RERANK_URL, headers=headers, json=payload)
    response.raise_for_status()

    data = response.json()
    # Each item: {"index": int, "relevance_score": float}
    ranked = sorted(data["data"], key=lambda x: x["relevance_score"], reverse=True)
    return [documents[item["index"]] for item in ranked[:top_k]]


async def rerank_documents(
    query: str,
    documents: list[str],
    top_k: int = 5,
    api_key: Optional[str] = None,
) -> list[str]:
    """
    Async wrapper around the Voyage rerank API.

    Args:
        query:     The user query to rank documents against.
        documents: List of document strings to rerank.
        top_k:     Maximum number of results to return.
        api_key:   Override key (defaults to config.voyage_api_key).

    Returns:
        List of document strings sorted by relevance (highest first), capped at top_k.
        Returns [] immediately if documents is empty.
    """
    if not documents:
        return []

    resolved_key = (api_key or voyage_api_key or "").strip()

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        _sync_rerank,
        query,
        documents,
        top_k,
        resolved_key,
    )
