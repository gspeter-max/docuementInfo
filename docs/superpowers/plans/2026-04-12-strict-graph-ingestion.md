# Strict Graph Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Execution Tracking Protocol (For Gemini CLI)

> **MANDATORY:** As the Gemini CLI agent implementing this plan, you MUST maintain a `### TASK BREAKDOWN` block in your internal reasoning and communicate your progress clearly using your core Iron Laws. 

When you start the session, you must establish this checklist and update it as you go:
```markdown
### TASK BREAKDOWN
- [ ] Task 1: Add Graph Extraction Models And Relationship Schema
- [ ] Task 2: Implement Per-Chunk Graph Extraction With Strict Relationship Enum
- [ ] Task 3: Add Code-First Entity Resolution Funnel
- [ ] Task 4: Add One Focused LLM Resolver For Ambiguous Entity Clusters
- [ ] Task 5: Rewrite Raw Extraction Results To Canonical Entity Names
- [ ] Task 6: Extend Neo4j Writes For Documents, Entities, Mentions, And Strict Relationships
- [ ] Task 7: Refactor `ingestion.py` Into A Readable Pipeline Coordinator
- [ ] Task 8: Run Focused Tests, Then Broader Regression Tests

Current: Task 1
Status: working on
```
**Rule:** You must mark checkboxes as `[x]` as you complete each major task. Do not skip tasks. Complete them sequentially and run the tests for each task before moving to the next.

**Goal:** Build a readable ingestion pipeline that stores chunk vectors in Neo4j, extracts entities and strict-schema relationships from chunks in parallel, resolves duplicate entity names with a code-first funnel plus one focused LLM cleanup pass, and writes canonical graph data with provenance.

**Architecture:** Keep the current chunking and contextual retrieval flow, then add a second graph extraction phase. Chunk-level LLM calls stay parallel and only use a fixed relationship schema; entity names stay open. After extraction, run exact match, fuzzy match, and embedding clustering to shrink duplicate entities, then run one LLM resolver call only on ambiguous clusters to decide merge or split and choose canonical names before persisting Neo4j entities and relationships.

**Tech Stack:** FastAPI, Neo4j, AsyncOpenAI-compatible client for Mistral, Jina embeddings, `rapidfuzz`, `pytest`, `respx`

---

## File Structure

**Context to Read First**

> **CRITICAL FOR NEW SESSIONS:** Before starting implementation, you MUST read and understand these existing files. This ensures you have the full context of the current architecture and prevents mistakes.

- `src/documentIngestion/ingestion.py`
  - Understand the current document parsing and contextual retrieval flow.
- `src/documentIngestion/models/ingestionModels.py`
  - Understand the existing Pydantic request/response structures.
- `src/db/neo4j/cypherQuerys.py`
  - See how Neo4j queries are currently structured, executed, and typed.
- `src/providers/llmProvider.py`
  - Understand the existing LLM client builder and how prompts are generally passed.
- `src/providers/embeddingModelProvider.py`
  - See how embeddings are generated and the provider interface.

**Existing files to modify**
- `src/documentIngestion/ingestion.py`
  - Orchestrates the full ingestion pipeline. This file should become a thin coordinator with readable helper calls.
- `src/documentIngestion/models/ingestionModels.py`
  - Keeps the request/response models. Add optional debug counters for extracted entities, canonical entities, and stored relationships.
- `src/db/neo4j/cypherQuerys.py`
  - Keeps all Neo4j writes and reads. Extend it to store `Document`, `Chunk`, `Entity`, `MENTIONS`, and strict relationship edges.
- `src/providers/llmProvider.py`
  - Continue using the shared LLM client builder. Add a helper for graph extraction prompts only if reuse improves readability.
- `src/providers/embeddingModelProvider.py`
  - Add a batch embedding method with readable naming so entity-resolution clustering can embed many candidate names in one request.
- `pyproject.toml`
  - Add `rapidfuzz` for fuzzy matching if it is not already present.

**New files to create**
- `src/documentIngestion/prompts/graph/extraction_system.md`
  - The system prompt instructions for graph extraction.
- `src/documentIngestion/prompts/graph/extraction_user.md`
  - The user prompt template for graph extraction.
- `src/documentIngestion/prompts/graph/resolution_system.md`
  - The system prompt instructions for entity resolution.
- `src/documentIngestion/prompts/graph/resolution_user.md`
  - The user prompt template for entity resolution.
- `src/documentIngestion/models/graphExtractionModels.py`
  - Typed data models for chunk extraction output, raw entities, raw relationships, canonical entities, and resolver decisions.
- `src/documentIngestion/graphRelationshipSchema.py`
  - The single source of truth for allowed relationship labels and prompt-friendly descriptions.
- `src/documentIngestion/graphExtraction.py`
  - Builds the strict relationship-schema prompt and runs one extraction call per chunk.
- `src/documentIngestion/entityResolution.py`
  - Performs exact normalization, fuzzy grouping, embedding clustering, ambiguous-cluster packaging, and mapping back to canonical names.
- `src/documentIngestion/graphPersistence.py`
  - Rewrites raw extraction results to canonical entity names and prepares Neo4j payloads.
- `tests/documentIngestion/test_graph_extraction.py`
  - Unit tests for strict-schema chunk extraction parsing and validation.
- `tests/documentIngestion/test_entity_resolution.py`
  - Unit tests for exact match, fuzzy grouping, embedding-band decisions, and resolver payload preparation.
- `tests/documentIngestion/test_graph_persistence.py`
  - Unit tests for canonical rewrite and Neo4j payload generation.
- `tests/documentIngestion/test_ingestion_pipeline.py`
  - End-to-end orchestration test with fake LLM and fake embedding responses.

## Readability Rules For This Implementation

- Every new function must include a docstring that explains:
  - what the function does
  - what input it expects
  - what it returns
- Prefer long descriptive names over clever short names.
- Keep each file focused on one responsibility.
- Move logic out of `ingestion.py` instead of growing one large coordinator file.
- Avoid inline comments except where a short note explains a non-obvious decision.

## Evaluation & Edge Case Testing Criteria

> **CRITICAL EVALUATION MANDATE:** The tests written for this plan act as your ultimate evaluation metric. Do not just write tests for the "happy path." You must write comprehensive tests that evaluate the system's resilience against real-world failures and edge cases. The AI implementing this plan will be judged by the quality and thoroughness of these tests.

When implementing the test steps below, you MUST expand them to cover:
- **Malformed LLM Responses:** Ensure tests evaluate how parsers handle missing JSON keys, incorrect data types, or completely unparseable garbage text from the LLM.
- **Empty Inputs:** Add tests for processing chunks with no entities found, lists with zero elements, or documents that yield no relationships.
- **Extreme Boundary Conditions:** Evaluate fuzzy matching with exact matches, completely dissimilar strings, and extremely long strings. Test resolution logic against conflicting scores.
- **Data Integrity:** Verify that duplicate relationships are perfectly deduplicated without data loss, and canonical mapping doesn't accidentally map unrelated entities.
- Every test file created MUST include at least one edge case or failure mode evaluation test alongside the basic functionality test.

## Current State vs Target State

**Before**
- `src/documentIngestion/ingestion.py` only builds contextual chunks, generates embeddings, and writes `Chunk` nodes.
- `src/db/neo4j/cypherQuerys.py` only knows how to create a vector index and store chunks.
- There is no graph extraction, no entity resolution, no canonical-name rewrite, and no document/entity relationship persistence.

**After**
- `src/documentIngestion/ingestion.py` coordinates five readable stages:
  1. parse and contextualize document chunks
  2. embed contextualized chunks
  3. extract raw entities and strict-schema relationships in parallel
  4. resolve duplicate entities with code-first filtering plus one focused LLM pass
  5. write chunks, entities, mentions, and canonical relationships to Neo4j
- `src/db/neo4j/cypherQuerys.py` stores both vectors and graph structure.
- Tests cover extraction, resolution, rewrite, and orchestration.

### Task 1: Add Graph Extraction Models And Relationship Schema

**Files:**
- Create: `src/documentIngestion/models/graphExtractionModels.py`
- Create: `src/documentIngestion/graphRelationshipSchema.py`
- Test: `tests/documentIngestion/test_graph_extraction.py`

- [ ] **Step 1: Write the failing tests for strict relationship labels**

```python
import pytest

from src.documentIngestion.graphRelationshipSchema import (
    ALLOWED_RELATIONSHIP_TYPES,
    get_relationship_schema_prompt_text,
)
from src.documentIngestion.models.graphExtractionModels import RawGraphRelationship


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/documentIngestion/test_graph_extraction.py -v`
Expected: FAIL with import errors because the new schema and models do not exist yet.

- [ ] **Step 3: Add typed models with readable names and docstrings**

```python
from pydantic import BaseModel, Field, field_validator


class RawGraphEntity(BaseModel):
    """This tells us about one name or thing we found in a small piece of text, before we check if we already found it before."""

    entity_name: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    evidence_text: str = Field(min_length=1)


class RawGraphRelationship(BaseModel):
    """This shows how two names or things are connected to each other in a piece of text, using only the connections we allow."""

    source_entity_name: str = Field(min_length=1)
    relationship_type: str = Field(min_length=1)
    target_entity_name: str = Field(min_length=1)
    evidence_text: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)

    @field_validator("relationship_type")
    @classmethod
    def validate_relationship_type(cls, value: str) -> str:
        from documentIngestion.graphRelationshipSchema import ALLOWED_RELATIONSHIP_TYPES

        if value not in ALLOWED_RELATIONSHIP_TYPES:
            raise ValueError(f"Unsupported relationship type: {value}")
        return value
```

- [ ] **Step 4: Add the shared relationship schema source**

```python
ALLOWED_RELATIONSHIP_TYPES = [
    "RELATED_TO",
    "PART_OF",
    "DEPENDS_ON",
    "ASSIGNED_TO",
    "BLOCKED_BY",
    "OWNS",
    "REPORTS_TO",
    "LOCATED_IN",
]


def get_relationship_schema_prompt_text() -> str:
    """This gives us the exact list of allowed connections as text, so we can tell the AI exactly what words to use when connecting things."""
    return "\n".join(
        f"- {relationship_type}"
        for relationship_type in ALLOWED_RELATIONSHIP_TYPES
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/documentIngestion/test_graph_extraction.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tests/documentIngestion/test_graph_extraction.py src/documentIngestion/models/graphExtractionModels.py src/documentIngestion/graphRelationshipSchema.py
git commit -m "feat: add graph extraction schema models"
```

**Expected Git Diff**

```diff
diff --git a/src/documentIngestion/graphRelationshipSchema.py b/src/documentIngestion/graphRelationshipSchema.py
new file mode 100644
+ALLOWED_RELATIONSHIP_TYPES = [
+    "RELATED_TO",
+    "PART_OF",
+    "DEPENDS_ON",
+    "ASSIGNED_TO",
+    "BLOCKED_BY",
+    "OWNS",
+    "REPORTS_TO",
+    "LOCATED_IN",
+]
```

### Task 2: Implement Per-Chunk Graph Extraction With Strict Relationship Enum

**Files:**
- Create: `src/documentIngestion/graphExtraction.py`
- Create: `src/documentIngestion/prompts/graph/extraction_system.md`
- Create: `src/documentIngestion/prompts/graph/extraction_user.md`
- Modify: `src/providers/llmProvider.py`
- Test: `tests/documentIngestion/test_graph_extraction.py`

- [ ] **Step 1: Extend the test file with one extraction parser test**

```python
from src.documentIngestion.graphExtraction import parse_chunk_graph_extraction_response


def test_parse_chunk_graph_extraction_response_returns_entities_and_relationships():
    """This test checks if we can correctly understand the answer the AI gives us and pull out the names and connections from it."""
    response_payload = {
        "entities": [
            {
                "entity_name": "Alice",
                "entity_type": "Person",
                "chunk_id": "resume.pdf::0",
                "evidence_text": "Alice works at Neo4j.",
            }
        ],
        "relationships": [
            {
                "source_entity_name": "Alice",
                "relationship_type": "RELATED_TO",
                "target_entity_name": "Neo4j",
                "evidence_text": "Alice works at Neo4j.",
                "chunk_id": "resume.pdf::0",
            }
        ],
    }

    result = parse_chunk_graph_extraction_response(response_payload)

    assert result.entities[0].entity_name == "Alice"
    assert result.relationships[0].relationship_type == "RELATED_TO"
```

- [ ] **Step 2: Run the new test to verify it fails**

Run: `pytest tests/documentIngestion/test_graph_extraction.py::test_parse_chunk_graph_extraction_response_returns_entities_and_relationships -v`
Expected: FAIL because `graphExtraction.py` does not exist.

- [ ] **Step 3: Implement readable extraction helpers**

```python
async def extract_graph_data_from_chunk(
    *,
    llm_client: AsyncOpenAI,
    chunk: dict[str, Any],
    model: str = DEFAULT_MODEL,
) -> ChunkGraphExtractionResult:
    """This function looks at a small piece of the text and asks the AI to find all the important names (like people or places) and how they connect to each other, like drawing lines between dots."""
    response = await llm_client.chat.completions.create(
        model=model,
        messages=build_graph_extraction_messages(chunk),
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    response_payload = json.loads(response.choices[0].message.content or "{}")
    return parse_chunk_graph_extraction_response(response_payload)
```

- [ ] **Step 4: Create prompt files and the prompt builder using them**

Create `src/documentIngestion/prompts/graph/extraction_system.md`:
```markdown
Extract entities and relationships from the chunk. Entity names and entity types are open-ended. Relationship types must be chosen only from this schema:
{schema_text}
```

Create `src/documentIngestion/prompts/graph/extraction_user.md`:
```markdown
Chunk id: {chunk_id}
Chunk text:
{chunk_text}

Return JSON with keys `entities` and `relationships`.
```

```python
from pathlib import Path

def build_graph_extraction_messages(chunk: dict[str, Any]) -> list[dict[str, str]]:
    """This function puts together the instructions and the text piece so we can ask the AI to find names and connections."""
    prompts_dir = Path(__file__).parent / "prompts" / "graph"
    system_prompt_template = (prompts_dir / "extraction_system.md").read_text(encoding="utf-8")
    user_prompt_template = (prompts_dir / "extraction_user.md").read_text(encoding="utf-8")

    return [
        {
            "role": "system",
            "content": system_prompt_template.format(
                schema_text=get_relationship_schema_prompt_text()
            ),
        },
        {
            "role": "user",
            "content": user_prompt_template.format(
                chunk_id=chunk["chunk_id"],
                chunk_text=chunk["text"]
            ),
        },
    ]
```

- [ ] **Step 5: Run the extraction tests**

Run: `pytest tests/documentIngestion/test_graph_extraction.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tests/documentIngestion/test_graph_extraction.py src/documentIngestion/graphExtraction.py src/providers/llmProvider.py
git add src/documentIngestion/prompts/graph
git commit -m "feat: add strict graph extraction per chunk"
```

**Expected Git Diff**

```diff
diff --git a/src/documentIngestion/graphExtraction.py b/src/documentIngestion/graphExtraction.py
new file mode 100644
+async def extract_graph_data_from_chunk(*, llm_client, chunk, model=DEFAULT_MODEL):
+    """This function looks at a small piece of the text and asks the AI to find all the important names (like people or places) and how they connect to each other, like drawing lines between dots."""
+    response_payload = await request_chunk_graph_json(llm_client=llm_client, chunk=chunk, model=model)
+    return parse_chunk_graph_extraction_response(response_payload)
```

### Task 3: Add Code-First Entity Resolution Funnel

**Files:**
- Create: `src/documentIngestion/entityResolution.py`
- Modify: `src/providers/embeddingModelProvider.py`
- Modify: `pyproject.toml`
- Test: `tests/documentIngestion/test_entity_resolution.py`

- [ ] **Step 1: Write failing tests for normalization, fuzzy grouping, and ambiguity filtering**

```python
from src.documentIngestion.entityResolution import (
    group_entities_by_normalized_name,
    find_fuzzy_merge_candidates,
    split_clear_cases_from_ambiguous_cases,
)


def test_group_entities_by_normalized_name_merges_case_only_differences():
    """This test makes sure that when we have the same name written with different capital letters, we group them as the exact same name."""
    grouped = group_entities_by_normalized_name(["Tesla", "tesla", "TESLA"])
    assert len(grouped) == 1


def test_find_fuzzy_merge_candidates_detects_company_suffix_variants():
    """This test makes sure we can find and group names that look very similar, like a company name with or without the word 'Inc'."""
    candidates = find_fuzzy_merge_candidates(["Apple", "Apple Inc", "Microsoft"])
    assert ("Apple", "Apple Inc") in candidates


def test_split_clear_cases_from_ambiguous_cases_keeps_mid_band_for_later_resolution():
    """This test checks that we can correctly separate the pairs of names that are super obvious from the pairs that are confusing and need the AI to look at them."""
    same_entity_pairs, ambiguous_pairs, different_entity_pairs = split_clear_cases_from_ambiguous_cases(
        [
            ("Elon Musk", "Elon Musk", 0.99),
            ("Elon Musk", "Mr Musk", 0.72),
            ("Elon Musk", "Apple", 0.11),
        ]
    )
    assert ambiguous_pairs == [("Elon Musk", "Mr Musk", 0.72)]
```

- [ ] **Step 2: Run the entity-resolution test file to verify it fails**

Run: `pytest tests/documentIngestion/test_entity_resolution.py -v`
Expected: FAIL with missing module imports.

- [ ] **Step 3: Add `rapidfuzz` and batch embeddings**

```diff
diff --git a/pyproject.toml b/pyproject.toml
@@
 dependencies = [
     "llama-parse>=0.1.0",
     "transformers>=4.40.0",
     "langchain-text-splitters>=0.3.0",
+    "rapidfuzz>=3.9.0",
     "pytest>=8.0.0",
 ]
```

```python
async def generate_embeddings_for_text_list(self, texts: list[str]) -> list[list[float]]:
    """This turns a list of words into a list of numbers all at once. These numbers help us understand what the words mean so we can find similar words later."""
    data = {
        "model": self.embedModel,
        "task": "retrieval.query",
        "input": texts,
    }
    response = requests.post(self.url, headers=self.headers, data=json.dumps(data))
    response.raise_for_status()
    response_payload = response.json()
    return [row["embedding"] for row in response_payload["data"]]
```

- [ ] **Step 4: Implement the code-first resolution module**

```python
def group_entities_by_normalized_name(raw_entity_names: list[str]) -> dict[str, list[str]]:
    """This function puts names that look exactly the same (except for capital letters or extra spaces) into groups, so we know they are the same thing."""
    grouped_names: dict[str, list[str]] = {}
    for raw_entity_name in raw_entity_names:
        normalized_name = " ".join(raw_entity_name.lower().strip().split())
        grouped_names.setdefault(normalized_name, []).append(raw_entity_name)
    return grouped_names


def find_fuzzy_merge_candidates(raw_entity_names: list[str], threshold: int = 88) -> list[tuple[str, str]]:
    """This function finds pairs of names that look very similar, like "Apple" and "Apple Inc", and puts them together so we can check if they mean the same thing."""
    fuzzy_merge_candidates: list[tuple[str, str]] = []
    for left_index, left_name in enumerate(raw_entity_names):
        for right_name in raw_entity_names[left_index + 1:]:
            if fuzz.ratio(left_name, right_name) >= threshold:
                fuzzy_merge_candidates.append((left_name, right_name))
    return fuzzy_merge_candidates
```

- [ ] **Step 5: Run the entity-resolution tests**

Run: `pytest tests/documentIngestion/test_entity_resolution.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/providers/embeddingModelProvider.py src/documentIngestion/entityResolution.py tests/documentIngestion/test_entity_resolution.py
git commit -m "feat: add code-first entity resolution funnel"
```

**Expected Git Diff**

```diff
diff --git a/src/documentIngestion/entityResolution.py b/src/documentIngestion/entityResolution.py
new file mode 100644
+def group_entities_by_normalized_name(raw_entity_names: list[str]) -> dict[str, list[str]]:
+    """This function puts names that look exactly the same (except for capital letters or extra spaces) into groups, so we know they are the same thing."""
+    grouped_names: dict[str, list[str]] = {}
+    for raw_entity_name in raw_entity_names:
+        normalized_name = " ".join(raw_entity_name.lower().strip().split())
+        grouped_names.setdefault(normalized_name, []).append(raw_entity_name)
+    return grouped_names
```

### Task 4: Add One Focused LLM Resolver For Ambiguous Entity Clusters

**Files:**
- Create: `src/documentIngestion/prompts/graph/resolution_system.md`
- Create: `src/documentIngestion/prompts/graph/resolution_user.md`
- Modify: `src/documentIngestion/models/graphExtractionModels.py`
- Modify: `src/documentIngestion/entityResolution.py`
- Test: `tests/documentIngestion/test_entity_resolution.py`

- [ ] **Step 1: Extend tests with resolver payload and resolver decision coverage**

```python
from src.documentIngestion.entityResolution import build_entity_resolution_review_payload


def test_build_entity_resolution_review_payload_only_contains_ambiguous_cases():
    """This test makes sure we only send the confusing pairs of names to the AI for review, and not the obvious ones."""
    payload = build_entity_resolution_review_payload(
        ambiguous_pairs=[
            ("Elon", "Mr Musk", 0.72),
            ("Board", "Board of Directors", 0.69),
        ]
    )

    assert len(payload["ambiguous_pairs"]) == 2
    assert payload["ambiguous_pairs"][0]["left_name"] == "Elon"
```

- [ ] **Step 2: Run the new resolver test to verify it fails**

Run: `pytest tests/documentIngestion/test_entity_resolution.py::test_build_entity_resolution_review_payload_only_contains_ambiguous_cases -v`
Expected: FAIL because the resolver helper is not implemented yet.

- [ ] **Step 3: Add the resolver request and response models**

```python
class AmbiguousEntityPairForResolution(BaseModel):
    """This holds two names that look a bit similar but we are not completely sure if they are the same thing, so we need to ask the AI to decide."""

    left_name: str
    right_name: str
    similarity_score: float


class EntityResolutionDecision(BaseModel):
    """This is the final answer from the AI about whether two names mean the same thing, and what the best name to use for both of them is."""

    left_name: str
    right_name: str
    should_merge: bool
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Create prompt files and implement the focused cleanup prompt and parser**

Create `src/documentIngestion/prompts/graph/resolution_system.md`:
```markdown
You are an expert entity resolution system. Look at pairs of entity names and decide if they refer to the exact same real-world thing.
```

Create `src/documentIngestion/prompts/graph/resolution_user.md`:
```markdown
Here are the pairs of names to review:
{payload_json}

Return JSON with a `decisions` array.
```

```python
from pathlib import Path
import json

def build_entity_resolution_messages(payload: dict[str, Any]) -> list[dict[str, str]]:
    """This function gets the right files with instructions to ask the AI if two names are the same."""
    prompts_dir = Path(__file__).parent / "prompts" / "graph"
    system_prompt = (prompts_dir / "resolution_system.md").read_text(encoding="utf-8")
    user_prompt_template = (prompts_dir / "resolution_user.md").read_text(encoding="utf-8")

    return [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": user_prompt_template.format(
                payload_json=json.dumps(payload, indent=2)
            ),
        },
    ]

async def resolve_ambiguous_entity_pairs(
    *,
    llm_client: AsyncOpenAI,
    ambiguous_pairs: list[tuple[str, str, float]],
    model: str = DEFAULT_MODEL,
) -> list[EntityResolutionDecision]:
    """This function asks the AI to look at pairs of names we are confused about, and decide if they are the same thing or different things."""
    payload = build_entity_resolution_review_payload(ambiguous_pairs)
    response = await llm_client.chat.completions.create(
        model=model,
        messages=build_entity_resolution_messages(payload),
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    response_payload = json.loads(response.choices[0].message.content or "{}")
    return [
        EntityResolutionDecision(**decision_row)
        for decision_row in response_payload["decisions"]
    ]
```

- [ ] **Step 5: Re-run the entity-resolution tests**

Run: `pytest tests/documentIngestion/test_entity_resolution.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/documentIngestion/models/graphExtractionModels.py src/documentIngestion/entityResolution.py tests/documentIngestion/test_entity_resolution.py
git add src/documentIngestion/prompts/graph
git commit -m "feat: add llm cleanup for ambiguous entity names"
```

**Expected Git Diff**

```diff
diff --git a/src/documentIngestion/entityResolution.py b/src/documentIngestion/entityResolution.py
@@
+async def resolve_ambiguous_entity_pairs(*, llm_client, ambiguous_pairs, model=DEFAULT_MODEL):
+    """This function asks the AI to look at pairs of names we are confused about, and decide if they are the same thing or different things."""
+    payload = build_entity_resolution_review_payload(ambiguous_pairs)
+    response = await llm_client.chat.completions.create(
+        model=model,
+        messages=build_entity_resolution_messages(payload),
+        temperature=0.0,
+        response_format={"type": "json_object"},
+    )
```

### Task 5: Rewrite Raw Extraction Results To Canonical Entity Names

**Files:**
- Create: `src/documentIngestion/graphPersistence.py`
- Test: `tests/documentIngestion/test_graph_persistence.py`

- [ ] **Step 1: Write failing tests for canonical-name rewrite**

```python
from src.documentIngestion.graphPersistence import rewrite_graph_results_to_canonical_entities


def test_rewrite_graph_results_to_canonical_entities_updates_relationship_endpoints():
    """This test checks that when we change a name to its best version, we also update all the connections that use that name to point to the new best version."""
    raw_results = [
        {
            "entities": [{"entity_name": "Mr Musk", "entity_type": "Person", "chunk_id": "doc::0", "evidence_text": "Mr Musk spoke."}],
            "relationships": [{"source_entity_name": "Mr Musk", "relationship_type": "RELATED_TO", "target_entity_name": "Tesla", "evidence_text": "Mr Musk leads Tesla.", "chunk_id": "doc::0"}],
        }
    ]
    canonical_name_map = {"Mr Musk": "Elon Musk", "Tesla": "Tesla"}

    rewritten = rewrite_graph_results_to_canonical_entities(raw_results, canonical_name_map)

    assert rewritten.relationships[0].source_entity_name == "Elon Musk"
```

- [ ] **Step 2: Run the new persistence test to verify it fails**

Run: `pytest tests/documentIngestion/test_graph_persistence.py -v`
Expected: FAIL because the persistence module does not exist.

- [ ] **Step 3: Implement canonical rewrite helpers**

```python
def rewrite_graph_results_to_canonical_entities(
    raw_chunk_graph_results: list[ChunkGraphExtractionResult],
    canonical_name_by_raw_name: dict[str, str],
) -> CanonicalGraphPersistencePayload:
    """This function takes all the names we found and changes them to the single best name we chose for them, so we can save them correctly."""
    rewritten_entities = []
    rewritten_relationships = []
    for chunk_graph_result in raw_chunk_graph_results:
        for entity in chunk_graph_result.entities:
            rewritten_entities.append({
                "canonical_name": canonical_name_by_raw_name.get(entity.entity_name, entity.entity_name),
                "entity_type": entity.entity_type,
                "chunk_id": entity.chunk_id,
                "evidence_text": entity.evidence_text,
            })
        for relationship in chunk_graph_result.relationships:
            rewritten_relationships.append({
                "source_entity_name": canonical_name_by_raw_name.get(relationship.source_entity_name, relationship.source_entity_name),
                "relationship_type": relationship.relationship_type,
                "target_entity_name": canonical_name_by_raw_name.get(relationship.target_entity_name, relationship.target_entity_name),
                "chunk_id": relationship.chunk_id,
                "evidence_text": relationship.evidence_text,
            })
    return CanonicalGraphPersistencePayload(entities=rewritten_entities, relationships=rewritten_relationships)
```

- [ ] **Step 4: Add duplicate-edge collapse**

```python
def merge_duplicate_relationship_payloads(
    relationship_payloads: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """This function takes many identical connections and squishes them into one, making sure we remember all the places we found them."""
    merged_relationships_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for relationship_payload in relationship_payloads:
        relationship_key = (
            relationship_payload["source_entity_name"],
            relationship_payload["relationship_type"],
            relationship_payload["target_entity_name"],
        )
        merged_relationships_by_key.setdefault(relationship_key, relationship_payload)
    return list(merged_relationships_by_key.values())
```

- [ ] **Step 5: Run the persistence tests**

Run: `pytest tests/documentIngestion/test_graph_persistence.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/documentIngestion/graphPersistence.py tests/documentIngestion/test_graph_persistence.py
git commit -m "feat: add canonical graph rewrite before persistence"
```

**Expected Git Diff**

```diff
diff --git a/src/documentIngestion/graphPersistence.py b/src/documentIngestion/graphPersistence.py
new file mode 100644
+def rewrite_graph_results_to_canonical_entities(raw_chunk_graph_results, canonical_name_by_raw_name):
+    """This function takes all the names we found and changes them to the single best name we chose for them, so we can save them correctly."""
+    rewritten_entities = []
+    rewritten_relationships = []
+    for chunk_graph_result in raw_chunk_graph_results:
+        rewritten_entities.extend(chunk_graph_result.entities)
+        rewritten_relationships.extend(chunk_graph_result.relationships)
+    return CanonicalGraphPersistencePayload(entities=rewritten_entities, relationships=rewritten_relationships)
```

### Task 6: Extend Neo4j Writes For Documents, Entities, Mentions, And Strict Relationships

**Files:**
- Modify: `src/db/neo4j/cypherQuerys.py`
- Test: `tests/documentIngestion/test_graph_persistence.py`

- [ ] **Step 1: Add a failing test that asserts the prepared payload contains document, mention, and relationship writes**

```python
from src.documentIngestion.graphPersistence import build_neo4j_graph_write_payload


def test_build_neo4j_graph_write_payload_contains_mentions_and_relationships():
    """This test makes sure that the package of data we send to the database contains all the names, where they were mentioned, and how they connect."""
    payload = build_neo4j_graph_write_payload(
        document_id="resume.pdf",
        canonical_entities=[{"canonical_name": "Elon Musk", "entity_type": "Person"}],
        rewritten_relationships=[{"source_entity_name": "Elon Musk", "relationship_type": "RELATED_TO", "target_entity_name": "Tesla"}],
    )

    assert payload["document_id"] == "resume.pdf"
    assert payload["relationships"][0]["relationship_type"] == "RELATED_TO"
```

- [ ] **Step 2: Run the graph-persistence tests to verify the new case fails**

Run: `pytest tests/documentIngestion/test_graph_persistence.py -v`
Expected: FAIL because the payload builder does not yet include the new structure.

- [ ] **Step 3: Add readable Neo4j write helpers**

```python
async def save_document_node(client: Neo4jClient, document_id: str, source_file: str) -> None:
    """This saves the main document file name into our database so we can link everything back to it."""
    query = """
    MERGE (document:Document {document_id: $document_id})
    SET document.source_file = $source_file
    """
    await client.execute_query(query, {"document_id": document_id, "source_file": source_file})


async def save_entity_nodes_and_relationships(
    client: Neo4jClient,
    graph_write_payload: dict[str, Any],
) -> None:
    """This function saves all the best names and how they connect into our graph database, so we can search through them later."""
    await client.execute_query(ENTITY_WRITE_QUERY, {"entities": graph_write_payload["entities"]})
    await client.execute_query(MENTION_WRITE_QUERY, {"mentions": graph_write_payload["mentions"]})
    await client.execute_query(RELATIONSHIP_WRITE_QUERY, {"relationships": graph_write_payload["relationships"]})
```

- [ ] **Step 4: Keep relationship schema strict at write time**

```python
query = """
UNWIND $relationships AS relationship_row
MATCH (source:Entity {canonical_name: relationship_row.source_entity_name})
MATCH (target:Entity {canonical_name: relationship_row.target_entity_name})
MERGE (source)-[relationship:RELATES_TO {
    relationship_type: relationship_row.relationship_type,
    document_id: relationship_row.document_id,
    chunk_id: relationship_row.chunk_id
}]->(target)
SET relationship.evidence_text = relationship_row.evidence_text
"""
```

- [ ] **Step 5: Run the persistence tests**

Run: `pytest tests/documentIngestion/test_graph_persistence.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/db/neo4j/cypherQuerys.py tests/documentIngestion/test_graph_persistence.py
git commit -m "feat: persist canonical graph data in neo4j"
```

**Expected Git Diff**

```diff
diff --git a/src/db/neo4j/cypherQuerys.py b/src/db/neo4j/cypherQuerys.py
@@
+async def save_document_node(client: Neo4jClient, document_id: str, source_file: str) -> None:
+    """This saves the main document file name into our database so we can link everything back to it."""
+    query = """
+    MERGE (document:Document {document_id: $document_id})
+    SET document.source_file = $source_file
+    """
+    await client.execute_query(query, {"document_id": document_id, "source_file": source_file})
```

### Task 7: Refactor `ingestion.py` Into A Readable Pipeline Coordinator

**Files:**
- Modify: `src/documentIngestion/ingestion.py`
- Modify: `src/documentIngestion/models/ingestionModels.py`
- Test: `tests/documentIngestion/test_ingestion_pipeline.py`

- [ ] **Step 1: Write the orchestration test first**

```python
import asyncio

from src.documentIngestion.ingestion import ingest_document_graph


def test_ingest_document_graph_runs_all_pipeline_stages(monkeypatch):
    """This test watches the big boss function to make sure it runs all the required steps in the right order without skipping anything."""
    recorded_stage_names = []

    async def fake_build_contextualized_document(**kwargs):
        recorded_stage_names.append("context")
        return {
            "document_id": "resume.pdf",
            "source_file": "data/resume.pdf",
            "chunks": [{"chunk_id": "resume.pdf::0", "chunk_index": 0, "text": "Alice works at Neo4j.", "context": "Work section", "contextualized_text": "Work section\n\nAlice works at Neo4j."}],
        }

    async def fake_generate_embeddings_for_text_list(texts):
        recorded_stage_names.append("embed")
        return [[0.1, 0.2, 0.3]]

    async def fake_extract_chunk_graph_data_in_parallel(**kwargs):
        recorded_stage_names.append("extract")
        return []

    monkeypatch.setattr("src.documentIngestion.ingestion.build_contextualized_document", fake_build_contextualized_document)
    monkeypatch.setattr("src.documentIngestion.ingestion.build_contextualized_chunk_embeddings", fake_generate_embeddings_for_text_list)
    monkeypatch.setattr("src.documentIngestion.ingestion.extract_chunk_graph_data_in_parallel", fake_extract_chunk_graph_data_in_parallel)
    monkeypatch.setattr("src.documentIngestion.ingestion.resolve_entities_for_graph", lambda **kwargs: recorded_stage_names.append("resolve") or {"canonical_name_by_raw_name": {}})
    monkeypatch.setattr("src.documentIngestion.ingestion.persist_document_graph", lambda **kwargs: recorded_stage_names.append("persist"))

    asyncio.run(ingest_document_graph(file_path="data/resume.pdf"))

    assert recorded_stage_names == ["context", "embed", "extract", "resolve", "persist"]
```

- [ ] **Step 2: Run the orchestration test to verify it fails**

Run: `pytest tests/documentIngestion/test_ingestion_pipeline.py -v`
Expected: FAIL because the new coordinator function does not exist.

- [ ] **Step 3: Replace the one-file orchestration with named stages**

```python
async def ingest_document_graph(file_path: str) -> dict[str, int | str]:
    """This is the big boss function. It takes one document, breaks it into pieces, finds names and connections in each piece, cleans up the names so there are no duplicates, and saves everything into the database."""
    contextualized_document = await build_contextualized_document(file_path=file_path, client=await build_mistral_client())
    contextualized_chunk_embeddings = await build_contextualized_chunk_embeddings(contextualized_document["chunks"])
    raw_chunk_graph_results = await extract_chunk_graph_data_in_parallel(contextualized_document["chunks"])
    canonical_resolution_result = await resolve_entities_for_graph(raw_chunk_graph_results)
    await persist_document_graph(contextualized_document, contextualized_chunk_embeddings, raw_chunk_graph_results, canonical_resolution_result)
    return build_ingestion_summary_response(contextualized_document, raw_chunk_graph_results, canonical_resolution_result)
```

- [ ] **Step 4: Keep the FastAPI route thin**

```python
@ingestionRouter.post("/ingest", response_model=ingestionResponse)
async def ingest_document(request: ingestionRequest):
    """This gets the request from the web when someone wants to process a document, and hands it over to the big boss function to do the work."""
    return ingestionResponse(**await ingest_document_graph(request.file_path))
```

- [ ] **Step 5: Add response counters for easy verification**

```python
class ingestionResponse(BaseModel):
    status: str
    message: str
    raw_entity_count: int = 0
    canonical_entity_count: int = 0
    relationship_count: int = 0
```

- [ ] **Step 6: Run the orchestration tests**

Run: `pytest tests/documentIngestion/test_ingestion_pipeline.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/documentIngestion/ingestion.py src/documentIngestion/models/ingestionModels.py tests/documentIngestion/test_ingestion_pipeline.py
git commit -m "refactor: turn ingestion route into graph pipeline coordinator"
```

**Expected Git Diff**

```diff
diff --git a/src/documentIngestion/ingestion.py b/src/documentIngestion/ingestion.py
@@
-async def ingest_document(request: ingestionRequest):
-    try:
-        embedding_model = embeddingModel(
-            api_key=jina_api_key,
-            base_url="https://api.jina.ai/v1/embeddings",
-            embeddingModel="jina-embeddings-v2-base-en",
-            max_concurrency=10,
-        )
+async def ingest_document_graph(file_path: str) -> dict[str, int | str]:
+    """This is the big boss function. It takes one document, breaks it into pieces, finds names and connections in each piece, cleans up the names so there are no duplicates, and saves everything into the database."""
+    contextualized_document = await build_contextualized_document(file_path=file_path, client=await build_mistral_client())
+    raw_chunk_graph_results = await extract_chunk_graph_data_in_parallel(contextualized_document["chunks"])
+    canonical_resolution_result = await resolve_entities_for_graph(raw_chunk_graph_results)
```

### Task 8: Run Focused Tests, Then Broader Regression Tests

**Files:**
- Test only

- [ ] **Step 1: Run the new focused unit tests**

Run:

```bash
pytest tests/documentIngestion/test_graph_extraction.py -v
pytest tests/documentIngestion/test_entity_resolution.py -v
pytest tests/documentIngestion/test_graph_persistence.py -v
pytest tests/documentIngestion/test_ingestion_pipeline.py -v
```

Expected: All new tests PASS.

- [ ] **Step 2: Run the existing contextual retrieval tests to catch regressions**

Run:

```bash
pytest tests/documentIngestion/contextual_retrieval/test_contextual_retrieval_validation.py -v
pytest tests/documentIngestion/contextual_retrieval/test_contextual_retrieval_integration.py -v
```

Expected: PASS, or only known external-credit skips.

- [ ] **Step 3: Run the whole ingestion test package**

Run: `pytest tests/documentIngestion -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/documentIngestion
git commit -m "test: cover graph ingestion pipeline end to end"
```

## Final Before/After Snapshot

**Before**

```python
async def ingest_document(request: ingestionRequest):
    contextualized_document_chunk = await build_contextualized_document(
        file_path=request.file_path,
        client=await build_mistral_client(),
    )
    embeddings = await asyncio.gather(*[
        embedding_model.generateEmebedding(chunk["contextualized_text"])
        for chunk in chunks
    ])
    await asyncio.gather(*[
        save_chunk(neo4j_client, chunk, embedding)
        for chunk, embedding in zip(chunks, embeddings)
    ])
```

**After**

```python
async def ingest_document_graph(file_path: str) -> dict[str, int | str]:
    contextualized_document = await build_contextualized_document(file_path=file_path, client=await build_mistral_client())
    contextualized_chunk_embeddings = await build_contextualized_chunk_embeddings(contextualized_document["chunks"])
    raw_chunk_graph_results = await extract_chunk_graph_data_in_parallel(contextualized_document["chunks"])
    canonical_resolution_result = await resolve_entities_for_graph(raw_chunk_graph_results)
    canonical_graph_payload = rewrite_graph_results_to_canonical_entities(
        raw_chunk_graph_results,
        canonical_resolution_result["canonical_name_by_raw_name"],
    )
    await persist_document_graph(contextualized_document, contextualized_chunk_embeddings, canonical_graph_payload)
    return build_ingestion_summary_response(contextualized_document, canonical_graph_payload)
```

## Spec Coverage Check

- Strict relationship schema only: covered by `graphRelationshipSchema.py` and extraction-model validation.
- Open entity names and types: covered by raw entity models and extraction prompt wording.
- Parallel per-chunk LLM extraction: covered by `graphExtraction.py` and `ingestion.py` orchestration.
- Code-first dedupe before cleanup LLM: covered by `entityResolution.py`.
- One focused cleanup LLM pass only for ambiguous names: covered by resolver task.
- Neo4j vector storage plus graph storage: covered by `cypherQuerys.py` and persistence tasks.
- Readable naming and docstrings: required in the plan rules and repeated in each new module.

## Placeholder Scan

- No `TODO`
- No `TBD`
- No undefined future task references
- Every new code area has a file path, a failing test, an implementation step, a run command, and a commit command
