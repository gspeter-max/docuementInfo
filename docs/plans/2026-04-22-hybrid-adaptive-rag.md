# Hybrid Adaptive RAG Implementation Plan

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a `POST /query` endpoint that routes queries through Vector → Grader → Graph, re-ranking all collected context before generating a final answer.

**Architecture:** An LLM router classifies each query as `simple` or `complex`. Simple queries go through Vector search first, graded by an LLM; if insufficient, they escalate to Graph. Complex queries go straight to Vector + Graph in parallel. All collected context is re-ranked by Voyage AI before the final LLM answer call.

**Tech Stack:** Python, FastAPI, Mistral (via AsyncOpenAI), Voyage AI reranker, Neo4j, Jina embeddings, Pydantic.

---

## TODO Checklist (Follow in Order)

> Track progress by checking each box as you complete it.

### Task 1 — Voyage API Key
- [ ] Write test `tests/retrieve/test_config.py`
- [ ] Run test → confirm FAIL
- [ ] Add `voyage_api_key` to `src/config.py`
- [ ] Add `VOYAGE_API_KEY=...` to `.env`
- [ ] Run test → confirm PASS
- [ ] Commit: `feat: add VOYAGE_API_KEY to config`

### Task 2 — Voyage Reranker Provider
- [ ] Write tests `tests/retrieve/test_voyage_reranker.py`
- [ ] Run tests → confirm FAIL
- [ ] Create `src/providers/voyageRerankProvider.py`
- [ ] Run tests → confirm PASS
- [ ] Commit: `feat: add Voyage AI reranker provider`

### Task 3 — LLM Router
- [ ] Write tests `tests/retrieve/test_router.py`
- [ ] Run tests → confirm FAIL
- [ ] Create `src/documentRetrieve/router.py`
- [ ] Run tests → confirm PASS
- [ ] Commit: `feat: add LLM-based query intent router`

### Task 4 — LLM Grader
- [ ] Write tests `tests/retrieve/test_grader.py`
- [ ] Run tests → confirm FAIL
- [ ] Create `src/documentRetrieve/grader.py` (with `GraderResult` Pydantic model)
- [ ] Run tests → confirm PASS
- [ ] Commit: `feat: add LLM grader with sufficient/reason output`

### Task 5 — Graph Agent
- [ ] Add `fetch_entity_neighbors_1hop()` to `src/db/neo4j/cypherQuerys.py`
- [ ] Add `fetch_entity_neighbors_2hop()` to `src/db/neo4j/cypherQuerys.py`
- [ ] Write tests `tests/retrieve/test_graph_agent.py`
- [ ] Run tests → confirm FAIL
- [ ] Create `src/documentRetrieve/graphAgent.py`
- [ ] Run tests → confirm PASS
- [ ] Commit: `feat: add graph agent with adaptive 1-hop/2-hop traversal`

### Task 6 — Main Pipeline + POST /query
- [ ] Create `src/documentRetrieve/models.py` (QueryRequest, QueryResponse)
- [ ] Write tests `tests/retrieve/test_retrieve_pipeline.py`
- [ ] Run tests → confirm FAIL
- [ ] Implement `src/documentRetrieve/retrieve.py` (handle_query + route)
- [ ] Run tests → confirm PASS
- [ ] Commit: `feat: implement hybrid adaptive RAG pipeline with POST /query`

### Task 7 — Register Route
- [ ] Find where `ingestionRouter` is mounted in the app
- [ ] Add `retrieveRouter` in the same place
- [ ] Commit: `feat: register /query route in FastAPI app`

### Task 8 — Final Verification (git diff + self-check)
- [ ] Run `git diff main..HEAD` and read every changed line
- [ ] Self-check logic for each file (see Task 8 at the end of this plan)
- [ ] Run full test suite → confirm 14 tests pass
- [ ] Run ingestion tests → confirm nothing broken
- [ ] Commit final verification

---

### Task 1: Add Voyage API Key to Config

**Files:**
- Modify: `src/config.py`
- Modify: `.env` (add the key manually)

*What this does:* Loads `VOYAGE_API_KEY` from the environment for use by the reranker provider.

---

### Task 2: Voyage Reranker Provider

**Files:**
- Create: `src/providers/voyageRerankProvider.py`
- Test: `tests/retrieve/test_voyage_reranker.py`

*What this does:* Uses `requests` and `asyncio.get_event_loop().run_in_executor` to asynchronously call the `https://api.voyageai.com/v1/rerank` API using the `rerank-2` model, sorts results by `relevance_score`, and returns the top K strings.

---

### Task 3: LLM Router

**Files:**
- Create: `src/documentRetrieve/router.py`
- Test: `tests/retrieve/test_router.py`

*What this does:* Takes a query string and uses Mistral's structured output (`json_object`) to return `{"intent": "simple" | "complex"}`. If parsing fails, defaults to "simple". No keywords or regex, pure LLM routing.

---

### Task 4: LLM Grader

**Files:**
- Create: `src/documentRetrieve/grader.py`
- Test: `tests/retrieve/test_grader.py`

*What this does:* Analyzes chunks for a specific query and outputs a `GraderResult` (`sufficient: bool`, `reason: str`). If insufficient, the reason is logged and triggers graph escalation.

---

### Task 5: Graph Agent

**Files:**
- Create: `src/documentRetrieve/graphAgent.py`
- Modify: `src/db/neo4j/cypherQuerys.py`
- Test: `tests/retrieve/test_graph_agent.py`

*What this does:* Uses `entity_ids` to fetch 1-hop Cypher queries. If empty, falls back to 2-hop. Formats returned relationships as a readable plain text fact sheet for the LLM.

---

### Task 6: Main Pipeline + POST /query Route

**Files:**
- Modify: `src/documentRetrieve/retrieve.py`
- Create: `src/documentRetrieve/models.py`
- Test: `tests/retrieve/test_retrieve_pipeline.py`

*What this does:* Creates a FastAPI route `/query` returning `QueryResponse`. Wires together the intent routing, vector search, grading, graph escalation (adaptive/parallel), reranking, and final LLM response.

---

### Task 7: Register the Router in the App

**Files:**
- Modify: `src/__init__.py` or `main.py`

*What this does:* Mounts `retrieveRouter` into the main FastAPI application to make the endpoints live.

---

### Task 8: Final Verification — git diff + Self-Check

**This is the last task. Do not skip it.**

**Step 1: Run git diff against main**

```bash
git diff main..HEAD
```

Read every changed line in the diff. For each file, answer these questions before marking done:

**`src/config.py`**
- [ ] Is `voyage_api_key = os.environ.get("VOYAGE_API_KEY", "").strip()` present?
- [ ] Is it NOT raising an error if missing (unlike `llama_parse_api_key` which raises)?

**`src/providers/voyageRerankProvider.py`**
- [ ] Does it call `/v1/rerank` (not `/v1/embeddings`)?
- [ ] Does it use `run_in_executor` so sync `requests.post` doesn't block the event loop?
- [ ] Does it sort by `relevance_score` descending before slicing to top_k?
- [ ] Does it return `[]` safely when `documents` is empty?

**`src/documentRetrieve/router.py`**
- [ ] Does it use `response_format={"type": "json_object"}`?
- [ ] Does it default to `"simple"` on unexpected LLM output?
- [ ] Is there NO keyword matching or regex — only the LLM output is read?

**`src/documentRetrieve/grader.py`**
- [ ] Does `GraderResult` have both `sufficient: bool` AND `reason: str`?
- [ ] Is `reason` logged via structlog when `sufficient=False`?
- [ ] Does it default `sufficient=False` safely on JSON parse failure?

**`src/db/neo4j/cypherQuerys.py`**
- [ ] Does `fetch_entity_neighbors_1hop` match on `entity_id` (not `canonical_name`)?
- [ ] Does `fetch_entity_neighbors_2hop` use `*1..2` path depth?
- [ ] Do both queries return `source, rel_type, target, evidence_text`?

**`src/documentRetrieve/graphAgent.py`**
- [ ] Is 1-hop called FIRST and 2-hop called ONLY if 1-hop returns `[]`?
- [ ] Does it return `""` when both hops return nothing?
- [ ] Does `_rows_to_fact_sheet` produce one human-readable line per relationship?

**`src/documentRetrieve/retrieve.py`**
- [ ] On `complex` path — is the grader completely skipped?
- [ ] On `simple` path — is `escalated_to_graph=True` set when grader returns `sufficient=False`?
- [ ] Is `rerank_documents` called in BOTH paths before the final LLM answer call?
- [ ] Is `escalation_reason` set to `""` (empty string, not `None`) when not escalated?
- [ ] Does Neo4j client always close in a `finally` block?
- [ ] Are there no hardcoded API keys or URIs anywhere?

**Step 2: Run all new tests**

```bash
PYTHONPATH=src .venv/bin/pytest tests/retrieve/ -v
```

Expected — all 14 tests pass:
```
tests/retrieve/test_config.py::test_voyage_api_key_is_loaded                              PASSED
tests/retrieve/test_voyage_reranker.py::test_rerank_returns_top_n_sorted                  PASSED
...
14 passed
```

If any test fails — stop. Fix the failure before continuing.

**Step 3: Run existing ingestion tests**

```bash
PYTHONPATH=src .venv/bin/pytest tests/documentIngestion/ -v
```

Expected: all previously passing tests still pass. No regressions.

**Step 4: Final commit**

```bash
git add .
git commit -m "chore: final verification — 14 retrieve tests passing, no regressions"
```
