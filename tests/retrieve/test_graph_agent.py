"""
Task 5: Tests for the Graph Agent.
"""
from unittest.mock import AsyncMock, patch

import pytest

from documentRetrieve.graphAgent import gather_graph_facts


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_graph_agent_returns_empty_when_no_entities():
    """If entity_ids is empty, return empty string without calling DB."""
    mock_client = AsyncMock()
    result = await gather_graph_facts(mock_client, [])
    assert result == ""


@pytest.mark.anyio
async def test_graph_agent_uses_1hop_when_successful():
    """If 1-hop returns data, format it and don't call 2-hop."""
    mock_client = AsyncMock()
    
    mock_1hop_data = [
        {"source": "Alice", "rel_type": "KNOWS", "target": "Bob", "evidence_text": "Alice knows Bob."}
    ]

    with patch("documentRetrieve.graphAgent.fetch_entity_neighbors_1hop", return_value=mock_1hop_data) as mock_1hop, \
         patch("documentRetrieve.graphAgent.fetch_entity_neighbors_2hop") as mock_2hop:
         
        result = await gather_graph_facts(mock_client, ["Alice"])

    mock_1hop.assert_called_once_with(mock_client, ["Alice"])
    mock_2hop.assert_not_called()
    
    assert "Alice KNOWS Bob" in result
    assert "Alice knows Bob." in result


@pytest.mark.anyio
async def test_graph_agent_falls_back_to_2hop_if_1hop_empty():
    """If 1-hop returns empty, it must fall back to 2-hop."""
    mock_client = AsyncMock()
    
    mock_2hop_data = [
        {"source": "Alice", "rel_type": "REPORTS_TO", "target": "Charlie", "evidence_text": "Alice reports to Charlie."}
    ]

    with patch("documentRetrieve.graphAgent.fetch_entity_neighbors_1hop", return_value=[]) as mock_1hop, \
         patch("documentRetrieve.graphAgent.fetch_entity_neighbors_2hop", return_value=mock_2hop_data) as mock_2hop:
         
        result = await gather_graph_facts(mock_client, ["Alice"])

    mock_1hop.assert_called_once_with(mock_client, ["Alice"])
    mock_2hop.assert_called_once_with(mock_client, ["Alice"])
    
    assert "Alice REPORTS_TO Charlie" in result
    assert "Alice reports to Charlie." in result


@pytest.mark.anyio
async def test_graph_agent_returns_empty_if_both_hops_empty():
    """If both hops return empty, it returns an empty string."""
    mock_client = AsyncMock()

    with patch("documentRetrieve.graphAgent.fetch_entity_neighbors_1hop", return_value=[]) as mock_1hop, \
         patch("documentRetrieve.graphAgent.fetch_entity_neighbors_2hop", return_value=[]) as mock_2hop:
         
        result = await gather_graph_facts(mock_client, ["Alice"])

    mock_1hop.assert_called_once()
    mock_2hop.assert_called_once()
    assert result == ""
