import pytest

from src.documentIngestion.graphRelationshipSchema import (
    ALLOWED_RELATIONSHIP_TYPES,
    get_relationship_schema_prompt_text,
)
from src.documentIngestion.models.graphExtractionModels import RawGraphRelationship, RawGraphEntity


def test_relationship_schema_prompt_lists_every_allowed_relationship():
    """This test checks to make sure every connection type we allow is written down in the instructions we give to the AI."""
    prompt_text = get_relationship_schema_prompt_text()

    for relationship_type in ALLOWED_RELATIONSHIP_TYPES:
        assert relationship_type in prompt_text


def test_raw_graph_relationship_rejects_unknown_relationship_type():
    """This test makes sure that if the AI tries to use a connection type we did not allow, we throw an error and stop it."""
    with pytest.raises(ValueError):
        RawGraphRelationship(
            source_entity_name="Alice",
            relationship_type="WORKS",
            target_entity_name="Neo4j",
            evidence_text="Alice works at Neo4j.",
            chunk_id="resume.pdf::0",
        )

def test_raw_graph_entity_rejects_empty_evidence_text():
    """This edge-case test makes sure our system properly catches errors if the AI gives us an empty string for evidence."""
    with pytest.raises(ValueError):
        RawGraphEntity(
            entity_name="Alice",
            entity_type="Person",
            chunk_id="doc::0",
            evidence_text="",
        )
