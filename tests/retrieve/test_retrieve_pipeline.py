"""
Task 6: Tests for the main retrieve pipeline and endpoint.
"""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.models.retrieveModels import QueryRequest
from documentRetrieve.retrieve import handle_query

# Import the router from its new home in app/
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'app'))
from app.retrieveAPI import retrieveRouter

# Setup a dummy app to test the router
app = FastAPI()
app.include_router(retrieveRouter)
client = TestClient(app)


class MockGraderResult:
    def __init__(self, sufficient, reason, answer=""):
        self.sufficient = sufficient
        self.reason = reason
        self.answer = answer


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
@patch("documentRetrieve.retrieve.embeddingModel")
@patch("documentRetrieve.retrieve.Neo4jClient")
@patch("documentRetrieve.retrieve.build_mistral_client")
@patch("documentRetrieve.retrieve.classify_intent", return_value="complex")
@patch("documentRetrieve.retrieve.retrieve_similar_chunks", return_value=[{"full_context": "vec chunk", "chunk_id": "c1"}])
@patch("documentRetrieve.retrieve.extract_entity_ids_from_chunks", return_value=["Ent1"])
@patch("documentRetrieve.retrieve.gather_graph_facts", return_value="GRAPH FACTS")
@patch("documentRetrieve.retrieve.rerank_documents", return_value=["reranked vec chunk", "reranked graph chunk"])
async def test_complex_query_path(
    mock_rerank, mock_gather, mock_extract, mock_retrieve, mock_classify, mock_build_mistral, mock_neo4j, mock_embed
):
    """
    Complex queries must skip the grader, go straight to Graph, then rerank.
    """
    mock_neo4j.return_value.close = AsyncMock()
    mock_embed.return_value.generateEmebedding = AsyncMock(return_value=[0.1, 0.2])

    mock_llm_client = AsyncMock()
    mock_llm_client.chat.completions.create.return_value.choices = [
        AsyncMock(message=AsyncMock(content="Final Answer"))
    ]
    mock_build_mistral.return_value = mock_llm_client

    with patch("documentRetrieve.retrieve.grade_chunks") as mock_grade:
        req = QueryRequest(query="complex query test", top_k=5, top_k_rerank=3)
        res = await handle_query(req)

        # Grader must be skipped
        mock_grade.assert_not_called()

    # Intent
    assert res.intent == "complex"
    assert res.used_graph_search is True
    assert res.reason_for_graph_search == ""
    assert res.answer == "Final Answer"

    # Verify context passed to rerank contains both vector and graph chunks
    rerank_docs_arg = mock_rerank.call_args[1]["documents"]
    assert "vec chunk" in rerank_docs_arg
    assert "GRAPH FACTS" in rerank_docs_arg


@pytest.mark.anyio
@patch("documentRetrieve.retrieve.embeddingModel")
@patch("documentRetrieve.retrieve.Neo4jClient")
@patch("documentRetrieve.retrieve.build_mistral_client")
@patch("documentRetrieve.retrieve.classify_intent", return_value="simple")
@patch("documentRetrieve.retrieve.retrieve_similar_chunks", return_value=[{"full_context": "vec chunk", "chunk_id": "c1"}])
@patch("documentRetrieve.retrieve.grade_chunks", return_value=MockGraderResult(True, "looks good", answer="Final Answer"))
@patch("documentRetrieve.retrieve.rerank_documents", return_value=["reranked vec chunk"])
async def test_simple_query_sufficient_path(
    mock_rerank, mock_grade, mock_retrieve, mock_classify, mock_build_mistral, mock_neo4j, mock_embed
):
    """
    Simple queries that are sufficient must NOT call graph.
    """
    mock_neo4j.return_value.close = AsyncMock()
    mock_embed.return_value.generateEmebedding = AsyncMock(return_value=[0.1, 0.2])

    mock_llm_client = AsyncMock()
    mock_llm_client.chat.completions.create.return_value.choices = [
        AsyncMock(message=AsyncMock(content="Final Answer"))
    ]
    mock_build_mistral.return_value = mock_llm_client

    with patch("documentRetrieve.retrieve.extract_entity_ids_from_chunks") as mock_extract, \
         patch("documentRetrieve.retrieve.gather_graph_facts") as mock_gather:
        
        req = QueryRequest(query="simple query test", top_k=5, top_k_rerank=3)
        res = await handle_query(req)

        # Graph must be skipped
        mock_extract.assert_not_called()
        mock_gather.assert_not_called()

    assert res.intent == "simple"
    assert res.used_graph_search is False
    assert res.reason_for_graph_search == ""
    assert res.answer == "Final Answer"


@pytest.mark.anyio
@patch("documentRetrieve.retrieve.embeddingModel")
@patch("documentRetrieve.retrieve.Neo4jClient")
@patch("documentRetrieve.retrieve.build_mistral_client")
@patch("documentRetrieve.retrieve.classify_intent", return_value="simple")
@patch("documentRetrieve.retrieve.retrieve_similar_chunks", return_value=[{"full_context": "vec chunk", "chunk_id": "c1"}])
@patch("documentRetrieve.retrieve.grade_chunks", return_value=MockGraderResult(False, "missing details"))
@patch("documentRetrieve.retrieve.extract_entity_ids_from_chunks", return_value=["Ent1"])
@patch("documentRetrieve.retrieve.gather_graph_facts", return_value="GRAPH FACTS")
@patch("documentRetrieve.retrieve.rerank_documents", return_value=["reranked chunk"])
async def test_simple_query_insufficient_path(
    mock_rerank, mock_gather, mock_extract, mock_grade, mock_retrieve, mock_classify, mock_build_mistral, mock_neo4j, mock_embed
):
    """
    Simple queries that are insufficient must escalate to graph.
    """
    mock_neo4j.return_value.close = AsyncMock()
    mock_embed.return_value.generateEmebedding = AsyncMock(return_value=[0.1, 0.2])

    mock_llm_client = AsyncMock()
    mock_llm_client.chat.completions.create.return_value.choices = [
        AsyncMock(message=AsyncMock(content="Final Answer"))
    ]
    mock_build_mistral.return_value = mock_llm_client

    req = QueryRequest(query="simple query test", top_k=5, top_k_rerank=3)
    res = await handle_query(req)

    assert res.intent == "simple"
    assert res.used_graph_search is True
    assert res.reason_for_graph_search == "missing details"
    assert res.answer == "Final Answer"


def test_api_route():
    """Verify the /retrieve/query endpoint works and delegates properly."""
    # Patch where the function is *called from*, which is app.retrieveAPI
    with patch("app.retrieveAPI.handle_query") as mock_handle:
        from app.models.retrieveModels import QueryResponse
        mock_handle.return_value = QueryResponse(
            answer="test answer",
            intent="simple",
            used_graph_search=False,
            reason_for_graph_search="",
            context_used=["chunk"]
        )
        
        response = client.post("/retrieve/query", json={"query": "test", "top_k": 5, "top_k_rerank": 3})
        
    assert response.status_code == 200
    assert response.json() == {
        "answer": "test answer",
        "intent": "simple",
        "used_graph_search": False,
        "reason_for_graph_search": "",
        "context_used": ["chunk"]
    }
