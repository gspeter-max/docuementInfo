"""
Deep tests for the retrieve pipeline and prompt contracts.

These tests verify:
- The system prompt for answer generation contains the context block
- The grader answer is used directly — no extra LLM call — on the fast path
- generate_final_answer makes exactly ONE LLM call
- generate_final_answer returns a fallback string when context is empty
- extract_entity_ids_from_chunks deduplicates correctly
- extract_entity_ids_from_chunks handles missing/None entity_ids safely
- The pipeline does NOT call rerank or the final LLM when grader returns sufficient
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from documentRetrieve.retrieve import (
    generate_final_answer,
    extract_entity_ids_from_chunks,
    handle_query,
)
from documentRetrieve.models import QueryRequest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_llm_response(content: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    return response


class MockGraderResult:
    def __init__(self, sufficient, reason, answer=""):
        self.sufficient = sufficient
        self.reason = reason
        self.answer = answer


# ── Tests: extract_entity_ids_from_chunks() ───────────────────────────────────

def test_extract_entity_ids_deduplicates():
    """Two chunks sharing an entity_id must yield only one copy of that id."""
    chunks = [
        {"entity_ids": ["ent-A", "ent-B"]},
        {"entity_ids": ["ent-B", "ent-C"]},
    ]
    result = extract_entity_ids_from_chunks(chunks)
    assert sorted(result) == ["ent-A", "ent-B", "ent-C"]


def test_extract_entity_ids_handles_missing_key():
    """Chunks without 'entity_ids' key must not crash the extractor."""
    chunks = [{"full_context": "text only, no entity_ids key"}]
    result = extract_entity_ids_from_chunks(chunks)
    assert result == []


def test_extract_entity_ids_handles_none_value():
    """Chunks where entity_ids is None must not crash — they must be skipped."""
    chunks = [{"entity_ids": None}, {"entity_ids": ["ent-X"]}]
    result = extract_entity_ids_from_chunks(chunks)
    assert result == ["ent-X"]


def test_extract_entity_ids_empty_input():
    """Empty chunk list must return empty list."""
    assert extract_entity_ids_from_chunks([]) == []


def test_extract_entity_ids_empty_ids_list():
    """A chunk with entity_ids=[] must contribute nothing."""
    chunks = [{"entity_ids": []}, {"entity_ids": ["ent-1"]}]
    result = extract_entity_ids_from_chunks(chunks)
    assert result == ["ent-1"]


# ── Tests: generate_final_answer() ───────────────────────────────────────────

@pytest.mark.anyio
async def test_generate_final_answer_injects_context_into_prompt():
    """The system prompt sent to the LLM must contain the exact context text."""
    context_texts = ["UNIQUE_CONTEXT_BLOCK_12345"]
    llm_resp = _make_llm_response("The answer.")

    with patch("documentRetrieve.retrieve.build_mistral_client") as mock_builder:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=llm_resp)
        mock_builder.return_value = mock_client

        await generate_final_answer("query", context_texts)

        messages = mock_client.chat.completions.create.call_args[1]["messages"]
        system_msg = next(m["content"] for m in messages if m["role"] == "system")

    assert "UNIQUE_CONTEXT_BLOCK_12345" in system_msg, (
        "Context text must be injected into the system prompt"
    )


@pytest.mark.anyio
async def test_generate_final_answer_sends_query_as_user_message():
    """The user query must be sent as the user message, not injected into the system prompt."""
    llm_resp = _make_llm_response("An answer.")

    with patch("documentRetrieve.retrieve.build_mistral_client") as mock_builder:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=llm_resp)
        mock_builder.return_value = mock_client

        await generate_final_answer("MY_SPECIFIC_QUERY", ["some context"])

        messages = mock_client.chat.completions.create.call_args[1]["messages"]
        user_msg = next(m["content"] for m in messages if m["role"] == "user")

    assert "MY_SPECIFIC_QUERY" in user_msg


@pytest.mark.anyio
async def test_generate_final_answer_calls_llm_exactly_once():
    """generate_final_answer must call the LLM exactly once — not once per chunk."""
    llm_resp = _make_llm_response("Answer.")

    with patch("documentRetrieve.retrieve.build_mistral_client") as mock_builder:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=llm_resp)
        mock_builder.return_value = mock_client

        await generate_final_answer("q", ["chunk1", "chunk2", "chunk3"])

        assert mock_client.chat.completions.create.call_count == 1


@pytest.mark.anyio
async def test_generate_final_answer_returns_fallback_on_empty_context():
    """If context_texts is empty, must return a fallback string — never call LLM."""
    with patch("documentRetrieve.retrieve.build_mistral_client") as mock_builder:
        result = await generate_final_answer("q", [])
        mock_builder.assert_not_called()

    assert isinstance(result, str)
    assert len(result) > 0, "Fallback message must not be an empty string"


@pytest.mark.anyio
async def test_generate_final_answer_returns_fallback_on_llm_exception():
    """If the LLM call raises, must return an error string — never raise or crash."""
    with patch("documentRetrieve.retrieve.build_mistral_client") as mock_builder:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("LLM is down"))
        mock_builder.return_value = mock_client

        result = await generate_final_answer("q", ["context"])

    assert isinstance(result, str)
    assert len(result) > 0


# ── Tests: handle_query() fast path ──────────────────────────────────────────

@pytest.mark.anyio
async def test_pipeline_skips_final_llm_call_when_grader_is_sufficient():
    """
    On the fast path (grader sufficient=True), the pipeline must use the
    grader's pre-generated answer directly. It must NOT call generate_final_answer.
    """
    with patch("documentRetrieve.retrieve.embeddingModel") as mock_embed, \
         patch("documentRetrieve.retrieve.Neo4jClient") as mock_neo4j, \
         patch("documentRetrieve.retrieve.build_mistral_client"), \
         patch("documentRetrieve.retrieve.classify_intent", return_value="simple"), \
         patch("documentRetrieve.retrieve.retrieve_similar_chunks",
               return_value=[{"full_context": "some context", "chunk_id": "c1"}]), \
         patch("documentRetrieve.retrieve.grade_chunks",
               return_value=MockGraderResult(True, "", answer="GRADER_GENERATED_ANSWER")), \
         patch("documentRetrieve.retrieve.generate_final_answer") as mock_gen, \
         patch("documentRetrieve.retrieve.rerank_documents"), \
         patch("documentRetrieve.retrieve.gather_graph_facts"), \
         patch("documentRetrieve.retrieve.extract_entity_ids_from_chunks"):

        mock_neo4j.return_value.close = AsyncMock()
        mock_embed.return_value.generateEmebedding = AsyncMock(return_value=[0.1])

        req = QueryRequest(query="simple question", top_k=5, top_k_rerank=3)
        res = await handle_query(req)

        mock_gen.assert_not_called()

    assert res.answer == "GRADER_GENERATED_ANSWER"


@pytest.mark.anyio
async def test_pipeline_skips_rerank_when_grader_is_sufficient():
    """
    On the fast path, there is no new context to rerank — the grader already
    produced the final answer. rerank_documents must NOT be called.
    """
    with patch("documentRetrieve.retrieve.embeddingModel") as mock_embed, \
         patch("documentRetrieve.retrieve.Neo4jClient") as mock_neo4j, \
         patch("documentRetrieve.retrieve.build_mistral_client"), \
         patch("documentRetrieve.retrieve.classify_intent", return_value="simple"), \
         patch("documentRetrieve.retrieve.retrieve_similar_chunks",
               return_value=[{"full_context": "ctx", "chunk_id": "c1"}]), \
         patch("documentRetrieve.retrieve.grade_chunks",
               return_value=MockGraderResult(True, "", answer="fast answer")), \
         patch("documentRetrieve.retrieve.rerank_documents") as mock_rerank, \
         patch("documentRetrieve.retrieve.generate_final_answer"), \
         patch("documentRetrieve.retrieve.gather_graph_facts"), \
         patch("documentRetrieve.retrieve.extract_entity_ids_from_chunks"):

        mock_neo4j.return_value.close = AsyncMock()
        mock_embed.return_value.generateEmebedding = AsyncMock(return_value=[0.1])

        req = QueryRequest(query="q", top_k=5, top_k_rerank=3)
        await handle_query(req)

        mock_rerank.assert_not_called()


@pytest.mark.anyio
async def test_pipeline_response_fields_are_correct_on_fast_path():
    """
    On fast path: used_graph_search=False, reason_for_graph_search='',
    answer comes from grader, context_used is the raw vector texts.
    """
    with patch("documentRetrieve.retrieve.embeddingModel") as mock_embed, \
         patch("documentRetrieve.retrieve.Neo4jClient") as mock_neo4j, \
         patch("documentRetrieve.retrieve.build_mistral_client"), \
         patch("documentRetrieve.retrieve.classify_intent", return_value="simple"), \
         patch("documentRetrieve.retrieve.retrieve_similar_chunks",
               return_value=[{"full_context": "vector_text_here", "chunk_id": "c1"}]), \
         patch("documentRetrieve.retrieve.grade_chunks",
               return_value=MockGraderResult(True, "", answer="The answer.")), \
         patch("documentRetrieve.retrieve.rerank_documents"), \
         patch("documentRetrieve.retrieve.generate_final_answer"), \
         patch("documentRetrieve.retrieve.gather_graph_facts"), \
         patch("documentRetrieve.retrieve.extract_entity_ids_from_chunks"):

        mock_neo4j.return_value.close = AsyncMock()
        mock_embed.return_value.generateEmebedding = AsyncMock(return_value=[0.1])

        req = QueryRequest(query="q", top_k=5, top_k_rerank=3)
        res = await handle_query(req)

    assert res.used_graph_search is False
    assert res.reason_for_graph_search == ""
    assert res.answer == "The answer."
    assert "vector_text_here" in res.context_used
