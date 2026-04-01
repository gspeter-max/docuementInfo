# Contextual Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`<!-- - [ ] -->`) syntax for tracking.

**Goal:** Add the contextual retrieval stage that generates a short document-aware summary for each chunk, prepends that summary to the chunk text, and returns a structured payload ready for embedding and retrieval later.

**Architecture:** Keep chunking deterministic and reuse the existing parser plus recursive chunker. Add one orchestration module that owns Lightning AI client setup, prompt creation, per-chunk summary generation, and final output shaping. The real-environment runner will call the orchestration module and write a JSON artifact so later embedding/vector-store work can consume the exact same structure.

**Tech Stack:** `openai` Python client against Lightning AI's OpenAI-compatible API, `respx` for HTTP-level mocks, existing `llama-parse`, existing `transformers`, existing `langchain-text-splitters`, `pytest`

---
### Task 1: Add the Lightning AI client dependency and lock the integration contract

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `src/config.py`

<!-- - [ ] --> **Step 1: Update the dependency set** -->

```toml
[project]
dependencies = [
    "llama-parse>=0.1.0",
    "transformers>=4.40.0",
    "langchain-text-splitters>=0.3.0",
    "pytest>=8.0.0",
    "openai>=1.0.0",
    "respx>=0.21.0",
]
```

<!-- - [ ] --> **Step 1b: Extend `src/config.py` to expose both API keys**

```python
from pathlib import Path
import os

from dotenv import load_dotenv

_project_root = Path(__file__).resolve().parents[1]
load_dotenv(_project_root / ".env")

llama_parse_api_key = os.environ.get("LLAMA_PARSE_APIKEY", "").strip()
lightning_api_key = os.environ.get("LIGHTNING_API_KEY", "").strip()

if not llama_parse_api_key:
    raise EnvironmentError(
        "LLAMA_PARSE_APIKEY environment variable is not set. "
        "Please set it in your .env file or as an environment variable."
    )
```

<!-- - [ ] --> **Step 2: Sync the environment**

Run:

```bash
uv sync
```

Expected:
- `openai` is installed into `.venv`
- `uv.lock` is updated

<!-- - [ ] --> **Step 3: Verify the client import path**

Run:

```bash
uv run python - <<'PY'
from openai import OpenAI
print("OK", OpenAI.__name__)
PY
```

Expected:
- Prints `OK OpenAI`

<!-- - [ ] --> **Step 4: Commit**

```bash
git add pyproject.toml uv.lock src/config.py
git commit -m "feat: add lightning ai client dependency"
```

---

### Task 2: Write tests for the contextualization pipeline before implementation

**Files:**
- Create: `tests/documentIngestion/contextual_retrieval/__init__.py`
- Create: `tests/documentIngestion/contextual_retrieval/test_contextual_retrieval.py`
- Create: `tests/documentIngestion/contextual_retrieval/test_contextual_retrieval_integration.py`

<!-- - [ ] --> **Step 1: Write the failing tests**

```python
from types import SimpleNamespace

from src.documentIngestion.contextual_retrieval import (
    build_context_messages,
    build_contextualized_document,
    build_lightning_client,
    generate_chunk_context,
)


class FakeCompletions:
    def __init__(self, content: str):
        self.content = content
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.content)
                )
            ]
        )


class FakeClient:
    def __init__(self, content: str):
        self.chat = SimpleNamespace(completions=FakeCompletions(content))


def test_build_context_messages_mentions_chunk_and_document():
    chunk = {
        "chunk_index": 2,
        "text": "Experience section text",
        "token_count": 12,
        "document_id": "resume.pdf",
    }
    messages = build_context_messages(
        full_document_text="full document text",
        chunk=chunk,
    )

    assert messages[0]["role"] == "system"
    assert "retrieval context" in messages[0]["content"].lower()
    assert "resume.pdf" in messages[1]["content"]
    assert "chunk index: 2" in messages[1]["content"].lower()


def test_generate_chunk_context_adds_context_and_contextualized_text():
    client = FakeClient("This chunk describes the applicant's experience at Acme.")
    chunk = {
        "chunk_index": 0,
        "text": "Experience: built search pipelines.",
        "token_count": 6,
        "document_id": "resume.pdf",
    }

    result = generate_chunk_context(
        client=client,
        full_document_text="full document text",
        chunk=chunk,
        model="lightning-ai/gpt-oss-120b",
    )

    assert result["context"] == "This chunk describes the applicant's experience at Acme."
    assert result["contextualized_text"] == (
        "This chunk describes the applicant's experience at Acme.\n\n"
        "Experience: built search pipelines."
    )
    assert result["document_id"] == "resume.pdf"
    assert result["chunk_index"] == 0


def test_build_contextualized_document_returns_one_record_per_chunk(monkeypatch):
    from src.documentIngestion import contextual_retrieval as module

    monkeypatch.setattr(
        module,
        "parse_document",
        lambda file_path: [{"pages": [{"page": 1, "text": "page text", "md": "page md"}]}],
    )
    monkeypatch.setattr(module, "get_all_pages_text", lambda parsed: "page text")
    monkeypatch.setattr(
        module,
        "chunk_document",
        lambda text, document_id, chunk_size=512, chunk_overlap=100: [
            {
                "chunk_index": 0,
                "text": "page text",
                "token_count": 2,
                "document_id": document_id,
            }
        ],
    )

    client = FakeClient("A short retrieval context.")
    result = build_contextualized_document(
        file_path="data/sample.pdf",
        client=client,
        model="lightning-ai/gpt-oss-120b",
    )

    assert len(result["chunks"]) == 1
    assert result["chunks"][0]["context"] == "A short retrieval context."
    assert result["chunks"][0]["contextualized_text"].startswith("A short retrieval context.")


def test_build_contextualized_document_returns_empty_chunks_for_empty_document(monkeypatch):
    from src.documentIngestion import contextual_retrieval as module

    monkeypatch.setattr(module, "parse_document", lambda file_path: [{"pages": []}])
    monkeypatch.setattr(module, "get_all_pages_text", lambda parsed: "")
    monkeypatch.setattr(module, "chunk_document", lambda text, document_id, chunk_size=512, chunk_overlap=100: [])

    client = FakeClient("irrelevant")
    result = build_contextualized_document(
        file_path="data/sample.pdf",
        client=client,
        model="lightning-ai/gpt-oss-120b",
    )

    assert result["chunks"] == []
    assert result["chunk_count"] == 0


def test_generate_chunk_context_handles_empty_model_response():
    client = FakeClient("")
    chunk = {
        "chunk_index": 1,
        "text": "Skills: Python, SQL, and search infrastructure.",
        "token_count": 8,
        "document_id": "resume.pdf",
    }

    result = generate_chunk_context(
        client=client,
        full_document_text="full document text",
        chunk=chunk,
        model="lightning-ai/gpt-oss-120b",
    )

    assert result["context"] == ""
    assert result["contextualized_text"] == "\n\nSkills: Python, SQL, and search infrastructure."


def test_generate_chunk_context_propagates_client_error():
    class ErrorClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    raise TimeoutError("request timed out")

    chunk = {
        "chunk_index": 3,
        "text": "Education and certification details.",
        "token_count": 5,
        "document_id": "resume.pdf",
    }

    try:
        generate_chunk_context(
            client=ErrorClient(),
            full_document_text="full document text",
            chunk=chunk,
            model="lightning-ai/gpt-oss-120b",
        )
        assert False, "Expected TimeoutError"
    except TimeoutError:
        assert True


def test_build_contextualized_document_handles_expected_load(monkeypatch):
    from src.documentIngestion import contextual_retrieval as module

    monkeypatch.setattr(
        module,
        "parse_document",
        lambda file_path: [{"pages": [{"page": 1, "text": "page text", "md": "page md"}]}],
    )
    monkeypatch.setattr(module, "get_all_pages_text", lambda parsed: "page text")
    monkeypatch.setattr(
        module,
        "chunk_document",
        lambda text, document_id, chunk_size=512, chunk_overlap=100: [
            {
                "chunk_index": i,
                "text": f"chunk {i}",
                "token_count": 2,
                "document_id": document_id,
            }
            for i in range(100)
        ],
    )

    client = FakeClient("load context")
    result = build_contextualized_document(
        file_path="data/sample.pdf",
        client=client,
        model="lightning-ai/gpt-oss-120b",
    )

    assert result["chunk_count"] == 100
    assert len(result["chunks"]) == 100
    assert result["chunks"][99]["chunk_index"] == 99


def test_build_lightning_client_requires_explicit_key():
    try:
        build_lightning_client(api_key="")
        assert False, "Expected EnvironmentError"
    except EnvironmentError:
        assert True
```

<!-- - [ ] --> **Step 2: Run the tests and verify they fail first**

Run:

```bash
uv run pytest tests/documentIngestion/contextual_retrieval/test_contextual_retrieval.py -v
```

Expected:
- Fails with `ModuleNotFoundError` for `src.documentIngestion.contextual_retrieval` until the new module exists

<!-- - [ ] --> **Step 3: Commit the tests**

```bash
git add tests/documentIngestion/contextual_retrieval/
git commit -m "test: define contextual retrieval pipeline behavior"
```

<!-- - [ ] --> **Step 4: Add mock-based HTTP integration tests for realistic Lightning responses**

```python
import pytest
import respx
from httpx import Response

from src.documentIngestion.contextual_retrieval import build_lightning_client, generate_chunk_context


@respx.mock
def test_generate_chunk_context_with_realistic_openai_shape():
    route = respx.post("https://lightning.ai/api/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "lightning-ai/gpt-oss-120b",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "This chunk is part of the work experience section.",
                        },
                        "finish_reason": "stop",
                    }
                ],
            },
        )
    )

    client = build_lightning_client(api_key="test-key")
    chunk = {
        "chunk_index": 0,
        "text": "Built search pipelines.",
        "token_count": 3,
        "document_id": "resume.pdf",
    }

    result = generate_chunk_context(
        client=client,
        full_document_text="full document text",
        chunk=chunk,
        model="lightning-ai/gpt-oss-120b",
    )

    assert route.called
    assert result["context"] == "This chunk is part of the work experience section."
    assert result["contextualized_text"].startswith("This chunk is part of the work experience section.")


def test_build_lightning_client_requires_key():
    with pytest.raises(EnvironmentError):
        build_lightning_client(api_key="")
```

<!-- - [ ] --> **Step 5: Add the minimal real API smoke test**

```python
import pytest

from src.config import lightning_api_key
from src.documentIngestion.contextual_retrieval import build_lightning_client, generate_chunk_context


@pytest.mark.integration
def test_real_lightning_smoke():
    if not lightning_api_key:
        pytest.skip("LIGHTNING_API_KEY is not configured in src.config")

    client = build_lightning_client(api_key=lightning_api_key)
    chunk = {
        "chunk_index": 0,
        "text": "Experience: built and operated search systems.",
        "token_count": 7,
        "document_id": "resume.pdf",
    }

    result = generate_chunk_context(
        client=client,
        full_document_text="Full document text goes here.",
        chunk=chunk,
        model="lightning-ai/gpt-oss-120b",
    )

    assert isinstance(result["context"], str)
    assert result["context"].strip() != ""
```

<!-- - [ ] --> **Step 6: Run the tests and verify they fail first**

Run:

```bash
uv run pytest tests/documentIngestion/contextual_retrieval/test_contextual_retrieval.py -v
uv run pytest tests/documentIngestion/contextual_retrieval/test_contextual_retrieval_integration.py -v
```

Expected:
- Unit tests fail until implementation exists
- The integration test is skipped unless the Lightning API key is configured in `src.config`

---

### Task 3: Implement the one-file contextual retrieval pipeline

**Files:**
- Create: `src/documentIngestion/contextual_retrieval.py`

<!-- - [ ] --> **Step 1: Add the orchestration module**

```python
"""
Contextual retrieval pipeline.

This module parses a document, chunks the full text, generates a short
retrieval-oriented summary for each chunk, and returns contextualized chunks.
It does not embed text or write vectors.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openai import OpenAI

from src.documentIngestion.chunking import chunk_document
from src.documentIngestion.parseDocument import get_all_pages_text, parse_document
from src.config import lightning_api_key

LIGHTNING_BASE_URL = "https://lightning.ai/api/v1"
DEFAULT_MODEL = "lightning-ai/gpt-oss-120b"


def build_lightning_client(
    api_key: str | None = None,
    base_url: str = LIGHTNING_BASE_URL,
) -> OpenAI:
    resolved_api_key = (api_key or lightning_api_key).strip()
    if not resolved_api_key:
        raise EnvironmentError(
            "LIGHTNING_API_KEY is not set. "
            "Set it in your .env file, expose it from src.config, or pass it explicitly."
        )
    return OpenAI(api_key=resolved_api_key, base_url=base_url)


def build_context_messages(full_document_text: str, chunk: dict[str, Any]) -> list[dict[str, str]]:
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


def generate_chunk_context(
    *,
    client: OpenAI,
    full_document_text: str,
    chunk: dict[str, Any],
    model: str = DEFAULT_MODEL,
    max_tokens: int = 120,
) -> dict[str, Any]:
    messages = build_context_messages(full_document_text, chunk)
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.0,
        max_tokens=max_tokens,
    )
    context = response.choices[0].message.content.strip()
    contextualized_text = f"{context}\n\n{chunk['text']}"
    return {
        **chunk,
        "context": context,
        "contextualized_text": contextualized_text,
        "model": model,
    }


def build_contextualized_document(
    *,
    file_path: str,
    client: OpenAI,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    parsed = parse_document(file_path)
    full_document_text = get_all_pages_text(parsed)
    document_id = Path(file_path).name
    chunks = chunk_document(full_document_text, document_id=document_id)

    contextualized_chunks = [
        generate_chunk_context(
            client=client,
            full_document_text=full_document_text,
            chunk=chunk,
            model=model,
        )
        for chunk in chunks
    ]

    return {
        "document_id": document_id,
        "source_file": file_path,
        "full_document_text": full_document_text,
        "chunks": contextualized_chunks,
        "chunk_count": len(contextualized_chunks),
        "model": model,
    }
```

<!-- - [ ] --> **Step 2: Re-run the tests and verify they pass**

Run:

```bash
uv run pytest tests/documentIngestion/contextual_retrieval/test_contextual_retrieval.py -v
```

Expected:
- All tests pass

<!-- - [ ] --> **Step 3: Commit the implementation**

```bash
git add src/documentIngestion/contextual_retrieval.py
git commit -m "feat: add contextual retrieval pipeline"
```

---

### Task 4: Extend the real-environment runner to write contextualized JSON output

**Files:**
- Modify: `tests/real_env_test/run_real_env_test.py`
- Modify: `tests/real_env_test/real_env_test_results/`

<!-- - [ ] --> **Step 1: Update the runner to call the new contextual pipeline**

```python
from src.config import lightning_api_key
from src.documentIngestion.contextual_retrieval import (
    build_contextualized_document,
    build_lightning_client,
)

def main() -> int:
    parser = argparse.ArgumentParser(description="Run a manual real-environment PDF smoke test.")
    parser.add_argument("--pdf", required=True, help="Path to the PDF to parse and chunk.")
    parser.add_argument(
        "--output-dir",
        default="tests/real_env_test/real_env_test_results",
        help="Directory where the JSON report will be written.",
    )
    parser.add_argument(
        "--model",
        default="lightning-ai/gpt-oss-120b",
        help="Lightning AI model name to use for contextual summaries.",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf).expanduser().resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not lightning_api_key:
        raise EnvironmentError("LIGHTNING_API_KEY is not configured in src.config")

    client = build_lightning_client(api_key=lightning_api_key)
    report = build_contextualized_document(
        file_path=str(pdf_path),
        client=client,
        model=args.model,
    )

    output_path = output_dir / f"{pdf_path.stem}_contextualized.json"
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )

    print(f"Wrote report to: {output_path}")
    print(f"Chunks: {report['chunk_count']}")
    for chunk in report["chunks"]:
        print(f"Chunk {chunk['chunk_index']}: {chunk['token_count']} tokens")
        print(f"Context: {chunk['context']}")
```

<!-- - [ ] --> **Step 2: Run the real-environment script with the Lightning API key set**

Run:

```bash
export LIGHTNING_API_KEY="your-key-here"
uv run python tests/real_env_test/run_real_env_test.py --pdf data/pankajkumar.pdf
```

Expected:
- The script writes a JSON file into `tests/real_env_test/real_env_test_results/`
- Each chunk in the JSON includes `context` and `contextualized_text`
- The terminal prints the chunk index, token count, and generated context

<!-- - [ ] --> **Step 3: Commit the runner update**

```bash
git add tests/real_env_test/run_real_env_test.py tests/real_env_test/real_env_test_results/
git commit -m "feat: add contextual retrieval smoke test runner"
```

---

### Task 5: Verify the full contextual retrieval flow end to end

**Files:**
- No new files

<!-- - [ ] --> **Step 1: Run the unit tests**

Run:

```bash
uv run pytest tests/documentIngestion/chunking/test_recursive.py -v
uv run pytest tests/documentIngestion/contextual_retrieval/test_contextual_retrieval.py -v
uv run pytest tests/documentIngestion/contextual_retrieval/test_contextual_retrieval_integration.py -v
```

Expected:
- The existing chunking suite passes
- The new contextualization suite passes, including:
  - happy path flows
  - empty-document boundary cases
  - invalid input and client error propagation
  - realistic HTTP-mock responses
  - expected-load batch processing
- The integration test is skipped unless the Lightning API key is configured in `src.config`

<!-- - [ ] --> **Step 2: Run the manual smoke test**

Run:

```bash
export LIGHTNING_API_KEY="your-key-here"
uv run python tests/real_env_test/run_real_env_test.py --pdf data/pankajkumar.pdf
```

Expected:
- A JSON file appears in `tests/real_env_test/real_env_test_results/`
- The file includes a contextualized chunk list with one `contextualized_text` per chunk

<!-- - [ ] --> **Step 3: Commit the finished branch state**

```bash
git add src/documentIngestion/contextual_retrieval.py tests/documentIngestion/contextual_retrieval/ tests/real_env_test/run_real_env_test.py tests/real_env_test/real_env_test_results/ pyproject.toml uv.lock
git commit -m "feat: add contextual retrieval summary generation"
```

---

### Coverage Check

This plan covers the requested contextual retrieval stage:
- Parse the document
- Chunk the extracted text
- Generate a short summary for each chunk with Lightning AI
- Combine summary plus original chunk text into a contextualized chunk payload
- Write a real-environment JSON artifact for manual verification

It deliberately stops before embedding, vector storage, and retrieval query wiring.
