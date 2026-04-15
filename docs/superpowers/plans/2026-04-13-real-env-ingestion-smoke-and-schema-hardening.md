# Real Env Ingestion Smoke And Schema Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep relationship types on a fixed schema, make the LLM use `RELATED_TO` plus `evidence_text` for nuance, add fast automated tests that catch prompt drift before the real-environment smoke run, and make the smoke script always write a short failure report.

**Architecture:** Keep the code simple and local. Do not mutate the relationship schema at runtime. Keep the schema fixed, make the extraction prompt tell the model to use `RELATED_TO` when a more specific type does not fit, and preserve `evidence_text` so downstream retrieval can read the nuance later. The automated tests should stay fast and deterministic; the real-environment script stays manual and easy to inspect.

**Tech Stack:** Python 3.12, `pytest`, `pydantic`, existing FastAPI/Neo4j ingestion code, existing Mistral and Jina clients, standard library `json` and `pathlib`.

**Working notes for the next engineer:**
- The current workspace already has unrelated local edits in `src/documentIngestion/chunking/recursive.py` and some prompt files. Do not revert or overwrite unrelated changes.
- The real failure we reproduced is `SENDS_TO` being returned by the LLM and rejected by `ChunkGraphExtractionResult`.
- The smoke script currently aborts before it writes a report if a later stage fails. That is the main usability gap to fix.

---

## Planned Diffs At A Glance

```diff
diff --git a/tests/documentIngestion/test_graph_extraction.py b/tests/documentIngestion/test_graph_extraction.py
@@
+def test_parse_chunk_graph_extraction_response_rejects_unknown_relationship_type():
+    response_payload = {
+        "entities": [],
+        "relationships": [{
+            "source_entity_name": "Alice",
+            "relationship_type": "SENDS_TO",
+            "target_entity_name": "Neo4j",
+            "evidence_text": "Alice sends data to Neo4j.",
+            "chunk_id": "resume.pdf::0",
+        }],
+    }
+
+    with pytest.raises(pydantic.ValidationError):
+        parse_chunk_graph_extraction_response(response_payload)
```

```diff
diff --git a/src/documentIngestion/prompts/graph/extraction_system.md b/src/documentIngestion/prompts/graph/extraction_system.md
@@
-Extract entities and relationships from the chunk. Entity names and entity types are open-ended. 
-
-CRITICAL RULE: Relationship types MUST be chosen ONLY from this exact list. Do not invent new types. If no type fits perfectly, use "RELATED_TO".
-{schema_text}
+Extract entities and relationships from the chunk.
+Entity names and entity types are open-ended.
+
+Relationship types must be chosen only from this exact list:
+{schema_text}
+
+If no exact type fits, use "RELATED_TO".
+Use `evidence_text` to capture the specific wording that explains the relationship.
+
+Return JSON with exactly two keys: "entities" and "relationships".
```

```diff
diff --git a/tests/real_env_test/run_real_env_test.py b/tests/real_env_test/run_real_env_test.py
@@
+def write_report(output_dir: Path, pdf_path: Path, payload: dict[str, Any]) -> Path:
+    report_name = f"{pdf_path.stem}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
+    report_path = output_dir / report_name
+    report_path.write_text(json.dumps(payload, indent=2, default=convert_to_python_types), encoding="utf-8")
+    return report_path
```

---

### Task 1: Lock The Current Failure Into Fast Automated Tests

**Files:**
- Modify: `tests/documentIngestion/test_graph_extraction.py`
- Create: `tests/documentIngestion/test_prompt_contracts.py`
- Create: `tests/real_env_test/test_run_real_env_test.py`

- [ ] **Step 1: Write the failing tests first**

```python
import pytest
from pathlib import Path
import pydantic

from src.documentIngestion.graphExtraction import parse_chunk_graph_extraction_response


def test_parse_chunk_graph_extraction_response_rejects_unknown_relationship_type():
    response_payload = {
        "entities": [],
        "relationships": [
            {
                "source_entity_name": "Alice",
                "relationship_type": "SENDS_TO",
                "target_entity_name": "Neo4j",
                "evidence_text": "Alice sends data to Neo4j.",
                "chunk_id": "resume.pdf::0",
            }
        ],
    }

    with pytest.raises(pydantic.ValidationError):
        parse_chunk_graph_extraction_response(response_payload)

def test_extraction_prompt_mentions_related_to_as_fallback():
    prompt = Path("src/documentIngestion/prompts/graph/extraction_system.md").read_text(encoding="utf-8")
    assert 'use "RELATED_TO"' in prompt
    assert "Never invent a new relationship type" in prompt
    assert "evidence_text" in prompt
```

And add one smoke-script test that checks partial failure reporting:

```python
import asyncio
import json

def test_smoke_runner_writes_error_report_on_stage_failure(monkeypatch, tmp_path):
    from tests.real_env_test.run_real_env_test import run_pipeline_step_by_step

    async def fake_build_mistral_client():
        return object()

    async def fake_build_contextualized_document(*, file_path, client):
        return {
            "document_id": "resume.pdf",
            "source_file": str(file_path),
            "chunks": [{"chunk_id": "resume.pdf::0", "chunk_index": 0, "text": "x", "context": "y", "contextualized_text": "y"}],
        }

    async def fake_embeddings(chunks):
        return [[0.1]]

    async def fake_extract(*args, **kwargs):
        raise ValueError("unsupported relationship type: SENDS_TO")

    monkeypatch.setattr("tests.real_env_test.run_real_env_test.build_mistral_client", fake_build_mistral_client)
    monkeypatch.setattr("tests.real_env_test.run_real_env_test.build_contextualized_document", fake_build_contextualized_document)
    monkeypatch.setattr("tests.real_env_test.run_real_env_test.build_contextualized_chunk_embeddings", fake_embeddings)
    monkeypatch.setattr("tests.real_env_test.run_real_env_test.extract_chunk_graph_data_in_parallel", fake_extract)
    report_path = asyncio.run(run_pipeline_step_by_step(tmp_path / "resume.pdf", tmp_path))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "error"
    assert report["failed_stage"] == "graph_extraction"
    assert "SENDS_TO" in report["error_message"]
```

- [ ] **Step 2: Run the tests and confirm they fail for the current code**

Run:
```bash
pytest tests/documentIngestion/test_graph_extraction.py -v
pytest tests/documentIngestion/test_prompt_contracts.py -v
pytest tests/real_env_test/test_run_real_env_test.py -v
```

Expected:
- The new `SENDS_TO` test fails with `ValidationError` because unknown relationship types stay invalid.
- The smoke-script test fails because the current script does not write a report path on failure.

- [ ] **Step 3: Commit the failing tests**

```bash
git add tests/documentIngestion/test_graph_extraction.py tests/documentIngestion/test_prompt_contracts.py tests/real_env_test/test_run_real_env_test.py
git commit -m "test: capture graph extraction fallback and smoke failures"
```

---

### Task 2: Keep The Schema Fixed And Preserve Evidence Text

**Files:**
- Modify: `src/documentIngestion/prompts/graph/extraction_system.md`
- Modify: `src/documentIngestion/prompts/graph/extraction_user.md`
- Modify: `tests/documentIngestion/test_prompt_contracts.py`

- [ ] **Step 1: Update the extraction prompt to keep the schema fixed**

Keep the prompt short and specific:

```md
Extract entities and relationships from the chunk.
Entity names and entity types are open-ended.

Relationship types must be chosen only from this exact list:
{schema_text}

If no exact type fits, use "RELATED_TO".
Use `evidence_text` to capture the specific wording that explains the relationship.

Return JSON with exactly two keys: "entities" and "relationships".
```

- [ ] **Step 2: Add tests that keep the schema fixed**

Keep the strict parser test. Add one prompt contract test that checks the fallback instruction and the `evidence_text` instruction.

The existing persistence tests already prove `evidence_text` is written into the Neo4j payload, so no schema expansion or runtime fallback is needed.

- [ ] **Step 3: Run the focused tests**

Run:
```bash
pytest tests/documentIngestion/test_graph_extraction.py tests/documentIngestion/test_prompt_contracts.py tests/documentIngestion/test_graph_persistence.py -v
```

Expected:
- Unknown relationship types still fail validation.
- The prompt contract test passes.
- The persistence payload still contains `evidence_text`.

- [ ] **Step 4: Commit the prompt update**

```bash
git add src/documentIngestion/prompts/graph/extraction_system.md src/documentIngestion/prompts/graph/extraction_user.md tests/documentIngestion/test_prompt_contracts.py
git commit -m "docs: keep relationship schema fixed and preserve evidence text"
```

---

### Task 3: Tighten The Prompts So The Model Gets A Clearer Contract

**Files:**
- Modify: `src/documentIngestion/prompts/graph/extraction_system.md`
- Modify: `src/documentIngestion/prompts/graph/extraction_user.md`
- Modify: `src/documentIngestion/prompts/graph/resolution_system.md`
- Modify: `src/documentIngestion/prompts/graph/resolution_user.md`
- Modify: `tests/documentIngestion/test_prompt_contracts.py`

- [ ] **Step 1: Rewrite the prompt text in plain, short instructions**

Use direct language and repeat the fallback rule once, not ten times.

Extraction system prompt:

```md
Extract entities and relationships from the chunk.
Entity names and entity types are open-ended.

Relationship types must be chosen only from this exact list:
{schema_text}

If no type fits perfectly, use "RELATED_TO".
Never invent a new relationship type.

Return JSON with exactly two keys: "entities" and "relationships".
```

Extraction user prompt:

```md
Chunk id: {chunk_id}
Chunk text:
{chunk_text}

Return JSON with keys `entities` and `relationships`.
Use the exact chunk id above in every extracted object.
```

Resolution prompt cleanup:

```md
Look at the name pairs and decide whether they are the same real-world thing.
Merge only when you are confident.
If they should not merge, set `should_merge` to false and keep `canonical_name` empty.

Return JSON with a `decisions` array.
```

- [ ] **Step 2: Add prompt contract tests**

```python
from pathlib import Path


def test_extraction_prompt_contains_allowed_schema_and_fallback_rule():
    prompt = Path("src/documentIngestion/prompts/graph/extraction_system.md").read_text(encoding="utf-8")
    assert "RELATED_TO" in prompt
    assert "Do not invent new relationship type" in prompt or "Never invent a new relationship type" in prompt


def test_resolution_prompt_requires_exact_json_shape():
    prompt = Path("src/documentIngestion/prompts/graph/resolution_system.md").read_text(encoding="utf-8")
    assert "decisions" in prompt
    assert "canonical_name" in prompt
```

- [ ] **Step 3: Run the prompt tests**

Run:
```bash
pytest tests/documentIngestion/test_prompt_contracts.py -v
```

Expected:
- Prompt contract tests pass.
- The text is shorter, clearer, and easier to read in a fresh session.

- [ ] **Step 4: Commit the prompt cleanup**

```bash
git add src/documentIngestion/prompts/graph/extraction_system.md src/documentIngestion/prompts/graph/extraction_user.md src/documentIngestion/prompts/graph/resolution_system.md src/documentIngestion/prompts/graph/resolution_user.md tests/documentIngestion/test_prompt_contracts.py
git commit -m "docs: clarify graph extraction and resolution prompts"
```

---

### Task 4: Refactor The Smoke Script So It Always Writes A Useful Report

**Files:**
- Modify: `tests/real_env_test/run_real_env_test.py`
- Create: `tests/real_env_test/test_run_real_env_test.py`

- [ ] **Step 1: Split the script into small helpers**

Keep the behavior the same, but make the code easier to read:

```python
def write_report(output_dir: Path, pdf_path: Path, payload: dict[str, Any]) -> Path:
    report_name = f"{pdf_path.stem}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    report_path = output_dir / report_name
    report_path.write_text(json.dumps(payload, indent=2, default=convert_to_python_types), encoding="utf-8")
    return report_path
```

Keep `run_pipeline_step_by_step` mostly as-is. The only behavior change should be:
- track the current stage name before each step
- catch exceptions
- write one JSON report on both success and failure
- return the report path

The report should stay small:
- `status`
- `failed_stage`
- `error_message`
- `document_id`
- `chunk_count`
- `relationship_count`
- `output_path`

- [ ] **Step 2: Add the smoke-runner unit tests**

Focus on one thing: failure reporting. Do not turn the test into a full integration test.

```python
def test_smoke_runner_writes_partial_report_when_graph_extraction_fails(monkeypatch, tmp_path):
    import asyncio
    import json
    from tests.real_env_test.run_real_env_test import run_pipeline_step_by_step

    async def fake_build_mistral_client():
        return object()

    async def fake_build_contextualized_document(*, file_path, client):
        return {
            "document_id": "resume.pdf",
            "source_file": str(file_path),
            "chunks": [
                {
                    "chunk_id": "resume.pdf::0",
                    "chunk_index": 0,
                    "text": "Alice sends data to Neo4j.",
                    "context": "Work section",
                    "contextualized_text": "Work section\n\nAlice sends data to Neo4j.",
                }
            ],
        }

    async def fake_extract(*args, **kwargs):
        raise ValueError("unsupported relationship type: SENDS_TO")

    monkeypatch.setattr("tests.real_env_test.run_real_env_test.build_mistral_client", fake_build_mistral_client)
    monkeypatch.setattr("tests.real_env_test.run_real_env_test.build_contextualized_document", fake_build_contextualized_document)
    monkeypatch.setattr("tests.real_env_test.run_real_env_test.extract_chunk_graph_data_in_parallel", fake_extract)

    report_path = asyncio.run(run_pipeline_step_by_step(tmp_path / "resume.pdf", tmp_path))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "error"
    assert report["failed_stage"] == "graph_extraction"
    assert "SENDS_TO" in report["error_message"]
```

- [ ] **Step 3: Run the smoke-script tests**

Run:
```bash
pytest tests/real_env_test/test_run_real_env_test.py -v
```

Expected:
- Partial failure reporting works.
- The report is written even when a later stage fails.

- [ ] **Step 4: Run the real smoke script again**

Run:
```bash
uv run python tests/real_env_test/run_real_env_test.py --pdf data/pankajkumar.pdf
```

Expected:
- No `ValidationError` for `SENDS_TO`.
- A JSON report is written to `tests/real_env_test/real_env_test_results/`.
- The report includes a success status if Neo4j is reachable.
- If Neo4j or an API fails, the report still writes the failure stage and error message.

- [ ] **Step 5: Commit the smoke-script refactor**

```bash
git add tests/real_env_test/run_real_env_test.py tests/real_env_test/test_run_real_env_test.py
git commit -m "test: make real env smoke runner report failures"
```

---

### Task 5: Verify The Whole Flow And Record The Final State

**Files:**
- Modify: none unless a verification-only cleanup is needed

- [ ] **Step 1: Run the focused test sets**

Run:
```bash
pytest tests/documentIngestion/test_graph_extraction.py tests/documentIngestion/test_prompt_contracts.py tests/real_env_test/test_run_real_env_test.py -v
```

Expected:
- All focused tests pass.

- [ ] **Step 2: Run the broader ingestion tests**

Run:
```bash
pytest tests/documentIngestion -v
```

Expected:
- No regression in graph extraction, entity resolution, persistence payloads, or ingestion orchestration.

- [ ] **Step 3: Run the real-environment smoke script one more time**

Run:
```bash
uv run python tests/real_env_test/run_real_env_test.py --pdf data/pankajkumar.pdf
```

Expected:
- The script either succeeds end to end or writes a short error report.
- The report tells you the stage that failed and the reason, without extra noise.

- [ ] **Step 4: Capture the final git diff and summarize it**

Run:
```bash
git diff -- src/documentIngestion/graphExtraction.py src/documentIngestion/prompts/graph/extraction_system.md src/documentIngestion/prompts/graph/extraction_user.md src/documentIngestion/prompts/graph/resolution_system.md src/documentIngestion/prompts/graph/resolution_user.md tests/documentIngestion/test_graph_extraction.py tests/documentIngestion/test_prompt_contracts.py tests/real_env_test/run_real_env_test.py tests/real_env_test/test_run_real_env_test.py
```

Expected:
- The diff shows only the planned normalization, prompt cleanup, and smoke-script improvements.

- [ ] **Step 5: Final commit**

If the previous commits were kept per task, this step should usually be a no-op. If there is one final cleanup edit, stage only that file and commit it with the same message.

---

## Coverage Check

- The `SENDS_TO` failure is covered by Task 1 and Task 2.
- The prompt quality issue is covered by Task 3.
- The smoke script not writing a report on failure is covered by Task 4.
- Regression protection is covered by the focused tests in Tasks 1 through 4 and the broader verification in Task 5.

## Best Practices To Keep

- Keep each helper focused on one job.
- Fail with the stage name, not just a stack trace.
- Keep manual smoke checks manual; keep deterministic checks in `pytest`.
- Keep the report payload small and readable.
- Commit after each meaningful slice so later debugging has a clean history.
- Do not broaden the fix into a refactor beyond the files above.

## varificaiton 
    - use git diff and see all the change  ( self review the implementation like )
    - self review 
    - read whole files that is upated 
    