from pathlib import Path


def test_extraction_prompt_mentions_related_to_as_fallback_and_evidence_text():
    prompt = Path("src/documentIngestion/prompts/graph/extraction_system.md").read_text(encoding="utf-8")

    assert 'RELATED_TO' in prompt
    assert 'Never invent a new relationship type' in prompt
    assert 'evidence_text' in prompt


def test_resolution_prompt_requires_exact_json_shape():
    prompt = Path("src/documentIngestion/prompts/graph/resolution_system.md").read_text(encoding="utf-8")

    assert "decisions" in prompt
    assert "canonical_name" in prompt


def test_extraction_system_prompt_defines_explicit_json_keys():
    prompt = Path("src/documentIngestion/prompts/graph/extraction_system.md").read_text(encoding="utf-8")
    
    # Check for entity keys
    assert "entity_name" in prompt
    assert "entity_type" in prompt
    assert "chunk_id" in prompt
    
    # Check for relationship keys
    assert "source_entity_name" in prompt
    assert "target_entity_name" in prompt
    assert "relationship_type" in prompt


def test_extraction_user_prompt_contains_one_shot_example():
    prompt = Path("src/documentIngestion/prompts/graph/extraction_user.md").read_text(encoding="utf-8")
    
    assert "Example Output Format" in prompt or "Example" in prompt
    assert "Alice" in prompt # Basic check that example content exists
    assert "entity_name" in prompt # Check that the example uses the correct keys
