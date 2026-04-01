Contextual Chunking — Implementation Plan
For Claude: REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

Goal: Build a paragraph-aware, token-counted text chunker that splits a full document into overlapping chunks without breaking paragraphs, using the Jina v3 tokenizer.

Architecture: All page texts from LlamaParse are combined into one document string (Option B). The chunker uses LangChain's RecursiveCharacterTextSplitter with a custom length_function powered by AutoTokenizer.from_pretrained("jinaai/jina-embeddings-v3"). Chunks carry metadata (index, token count, source doc id). Context generation (LLM step) is NOT part of this plan — that comes next.

Tech Stack: transformers (AutoTokenizer), langchain-text-splitters (RecursiveCharacterTextSplitter), pytest

What Does This Module Do? (Plain English)
The Problem
When a document has 100 pages of text, you can't feed all of it to a retrieval system at once. You need to break it into smaller pieces ("chunks"). But if you cut randomly, you might slice a paragraph in half — meaning the beginning of an idea is in chunk 5 and the end is in chunk 6, and neither makes full sense alone.

The Solution — This Chunker
Combine all pages first → one big string of text
Try to split at paragraph boundaries (\n\n) first. If a paragraph is still too big, split at line breaks (\n), then sentences (.), then spaces
Overlap — the last 100 tokens of chunk N are repeated at the start of chunk N+1. This ensures no idea is "lost at the edge"
Count tokens correctly using the same tokenizer that the Jina embedding model will use — so "512 tokens" means 512 actual Jina tokens, not 512 words or characters
Output
Each chunk is a Python dict like:

python
{
    "chunk_index": 0,
    "text": "...the actual chunk text...",
    "token_count": 487,
    "document_id": "resume.pdf"
}
Repository Structure After This Plan
documentInFo/
├── src/
│   ├── __init__.py                               ← exists
│   ├── config.py                                 ← exists
│   └── documentIngestion/
│       ├── __init__.py                           ← exists
│       ├── parseDocument.py                      ← exists (touches nothing)
│       ├── ingestion.py                          ← exists, empty (touches nothing)
│       └── chunking/                             ← NEW FOLDER (extensible: add strategies here)
│           ├── __init__.py                       ← NEW — exports count_tokens, chunk_document
│           └── recursive.py                      ← NEW — RecursiveCharacterTextSplitter strategy
├── tests/
│   ├── __init__.py                               ← NEW
│   └── documentIngestion/                        ← mirrors src/documentIngestion/
│       ├── __init__.py                           ← NEW
│       └── chunking/                             ← mirrors src/documentIngestion/chunking/
│           ├── __init__.py                       ← NEW
│           └── test_recursive.py                 ← NEW — tests for recursive.py
├── docs/
│   └── plans/
│       └── 2026-04-01-contextual-chunking.md     ← this file
├── data/                                         ← exists
├── main.py                                       ← exists (touches nothing)
└── pyproject.toml                                ← MODIFY — add new deps
Rule: chunking/recursive.py is pure chunking logic ONLY — no LLM calls, no embedding. Text in, list of chunk dicts out.

Extensibility: When you add a new strategy later (e.g. semantic chunking), add semantic.py alongside recursive.py and expose it through chunking/__init__.py.

Import from outside: from src.documentIngestion.chunking import chunk_document, count_tokens

Dependencies to Add
Why these?

transformers — for AutoTokenizer (Jina v3 tokenizer)
langchain-text-splitters — for RecursiveCharacterTextSplitter (paragraph-aware splitting)
pytest — for tests
toml
[project]
dependencies = [
    "llama-parse>=0.1.0",
    "transformers>=4.40.0",
    "langchain-text-splitters>=0.3.0",
    "pytest>=8.0.0",
]
Task 1: Add Dependencies to pyproject.toml
Files:

Modify: pyproject.toml
Step 1: Update pyproject.toml

Replace the dependencies section with:

toml
[project]
name = "documentinfo"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "llama-parse>=0.1.0",
    "transformers>=4.40.0",
    "langchain-text-splitters>=0.3.0",
    "pytest>=8.0.0",
]
Step 2: Install dependencies

bash
uv sync
Expected output: Packages resolved and installed with no errors.

Step 3: Verify install

bash
python3 -c "from transformers import AutoTokenizer; print('OK')"
python3 -c "from langchain_text_splitters import RecursiveCharacterTextSplitter; print('OK')"
Expected: Both print OK

Step 4: Commit

bash
git add pyproject.toml uv.lock
git commit -m "feat: add transformers and langchain-text-splitters dependencies"
Task 2: Create Tests First (TDD)
Why tests first? You write what you WANT the code to do before writing the code itself. This forces clear thinking.

Files:

Create: tests/__init__.py
Create: tests/documentIngestion/__init__.py
Create: tests/documentIngestion/chunking/__init__.py
Create: tests/documentIngestion/chunking/test_recursive.py
No TODOs. No gaps. Every test is complete and runnable as written.

Step 1: Create the test directory structure

bash
mkdir -p tests/documentIngestion/chunking
touch tests/__init__.py
touch tests/documentIngestion/__init__.py
touch tests/documentIngestion/chunking/__init__.py
Step 2: Write the failing tests in tests/documentIngestion/chunking/test_recursive.py

python
"""
Tests for src/documentIngestion/chunker.py
What we are testing:
  1. count_tokens()  — returns correct token count for a text string
  2. chunk_document() — splits text into correctly-sized overlapping chunks
                        without breaking paragraphs
"""
import pytest
from src.documentIngestion.chunking import count_tokens, chunk_document
# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
SIMPLE_TEXT = "Hello world. " * 100  # ~300 tokens — fits in one chunk
MULTI_PARAGRAPH_TEXT = (
    "This is paragraph one. " * 30 + "\n\n" +
    "This is paragraph two. " * 30 + "\n\n" +
    "This is paragraph three. " * 30 + "\n\n" +
    "This is paragraph four. " * 30 + "\n\n" +
    "This is paragraph five. " * 30
)
# ---------------------------------------------------------------------------
# count_tokens tests
# ---------------------------------------------------------------------------
class TestCountTokens:
    def test_returns_integer(self):
        """count_tokens must return a plain int, not a list or tensor."""
        result = count_tokens("Hello world")
        assert isinstance(result, int)
    def test_empty_string(self):
        """Empty string should return 0 tokens (or a small number for special tokens)."""
        result = count_tokens("")
        assert result >= 0
    def test_longer_text_has_more_tokens(self):
        """More words = more tokens. This is a sanity check."""
        short = count_tokens("Hello")
        long = count_tokens("Hello world this is a longer piece of text")
        assert long > short
    def test_token_count_is_reasonable(self):
        """100 words should produce between 80 and 200 tokens (rough sanity)."""
        text = "word " * 100
        tokens = count_tokens(text)
        assert 80 <= tokens <= 200
# ---------------------------------------------------------------------------
# chunk_document tests
# ---------------------------------------------------------------------------
class TestChunkDocument:
    def test_returns_list(self):
        """chunk_document must return a list."""
        result = chunk_document(SIMPLE_TEXT, document_id="test.pdf")
        assert isinstance(result, list)
    def test_each_item_is_dict(self):
        """Every item in the returned list must be a dict."""
        result = chunk_document(SIMPLE_TEXT, document_id="test.pdf")
        for item in result:
            assert isinstance(item, dict)
    def test_required_keys_present(self):
        """Each chunk dict must have: chunk_index, text, token_count, document_id."""
        result = chunk_document(SIMPLE_TEXT, document_id="test.pdf")
        required_keys = {"chunk_index", "text", "token_count", "document_id"}
        for chunk in result:
            assert required_keys.issubset(chunk.keys()), (
                f"Missing keys: {required_keys - chunk.keys()}"
            )
    def test_chunk_index_sequential(self):
        """chunk_index values must be 0, 1, 2, ... in order."""
        result = chunk_document(MULTI_PARAGRAPH_TEXT, document_id="test.pdf")
        for i, chunk in enumerate(result):
            assert chunk["chunk_index"] == i
    def test_document_id_propagated(self):
        """document_id passed in must appear on every chunk."""
        doc_id = "my_resume.pdf"
        result = chunk_document(SIMPLE_TEXT, document_id=doc_id)
        for chunk in result:
            assert chunk["document_id"] == doc_id
    def test_no_chunk_exceeds_max_tokens(self):
        """No chunk should have more tokens than chunk_size (512)."""
        result = chunk_document(MULTI_PARAGRAPH_TEXT, document_id="test.pdf")
        for chunk in result:
            assert chunk["token_count"] <= 512, (
                f"Chunk {chunk['chunk_index']} has {chunk['token_count']} tokens (max 512)"
            )
    def test_token_count_matches_text(self):
        """token_count in the dict must match actual count_tokens(text)."""
        result = chunk_document(MULTI_PARAGRAPH_TEXT, document_id="test.pdf")
        for chunk in result:
            actual = count_tokens(chunk["text"])
            assert chunk["token_count"] == actual, (
                f"Chunk {chunk['chunk_index']}: stored {chunk['token_count']}, "
                f"actual {actual}"
            )
    def test_multiple_chunks_produced_for_long_text(self):
        """A text that is much longer than 512 tokens must produce multiple chunks."""
        # ~900 tokens of text — must split into at least 2 chunks
        long_text = "This is a test sentence with several words. " * 120
        result = chunk_document(long_text, document_id="test.pdf")
        assert len(result) >= 2, "Long text should produce at least 2 chunks"
    def test_short_text_produces_one_chunk(self):
        """Text under 512 tokens must produce exactly 1 chunk."""
        short_text = "Short document. Just a few sentences."
        result = chunk_document(short_text, document_id="test.pdf")
        assert len(result) == 1
    def test_custom_chunk_size(self):
        """chunk_size parameter must be respected."""
        result = chunk_document(
            MULTI_PARAGRAPH_TEXT,
            document_id="test.pdf",
            chunk_size=256,
            chunk_overlap=50
        )
        for chunk in result:
            assert chunk["token_count"] <= 256
    def test_text_is_not_empty_string(self):
        """No chunk should have an empty text field."""
        result = chunk_document(MULTI_PARAGRAPH_TEXT, document_id="test.pdf")
        for chunk in result:
            assert chunk["text"].strip() != ""
    def test_empty_document_returns_empty_list(self):
        """An empty string should produce an empty list, not crash."""
        result = chunk_document("", document_id="test.pdf")
        assert result == []
Step 3: Run tests — verify they ALL fail

bash
pytest tests/documentIngestion/chunking/test_recursive.py -v
Expected: ALL FAIL with ModuleNotFoundError: No module named 'src.documentIngestion.chunking' This is correct — the module doesn't exist yet.

Task 3: Implement chunker.py
Files:

Create: src/documentIngestion/chunking/__init__.py
Create: src/documentIngestion/chunking/recursive.py
No TODOs. No gaps. Both files are complete and runnable as written.

Step 1: Create src/documentIngestion/chunking/__init__.py

This file is the public face of the chunking package. It imports from the strategy files so callers never need to know which file implements what.

python
"""
src/documentIngestion/chunking/__init__.py
Public API for the chunking package.
Import from here — not from individual strategy files:
    from src.documentIngestion.chunking import chunk_document, count_tokens
To add a new strategy later:
    1. Create src/documentIngestion/chunking/<strategy_name>.py
    2. Implement chunk_document() and count_tokens() (or reuse shared ones)
    3. Export from this file
"""
from .recursive import chunk_document, count_tokens
__all__ = ["chunk_document", "count_tokens"]
Step 2: Write the implementation in src/documentIngestion/chunking/recursive.py

python
"""
recursive.py — Paragraph-aware, token-counted text chunker using RecursiveCharacterTextSplitter.
What this file does:
    Takes a long document string and splits it into overlapping chunks
    that respect paragraph boundaries. Each chunk is stored as a dict
    with its text, token count, index, and source document id.
What this file does NOT do:
    - It does NOT call any LLM
    - It does NOT embed anything
    - It does NOT read files from disk
    - It does NOT generate context summaries (that is the next step)
Dependencies:
    - transformers   → AutoTokenizer (Jina v3 tokenizer)
    - langchain_text_splitters → RecursiveCharacterTextSplitter
Token counting:
    Uses jinaai/jina-embeddings-v3 tokenizer so that "512 tokens" here
    means 512 actual Jina embedding tokens — not characters or words.
Chunk defaults:
    chunk_size    = 512 tokens
    chunk_overlap = 100 tokens
"""
import sys
import os
# ---------------------------------------------------------------------------
# Make the project root visible to Python's import system.
# Allows this file to be run directly OR imported as a module.
# ---------------------------------------------------------------------------
_project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
from transformers import AutoTokenizer
from langchain_text_splitters import RecursiveCharacterTextSplitter
# ---------------------------------------------------------------------------
# Tokenizer — loaded once at module level (expensive operation).
# trust_remote_code=True is required by the Jina model.
# ---------------------------------------------------------------------------
_TOKENIZER_MODEL = "jinaai/jina-embeddings-v3"
_tokenizer = AutoTokenizer.from_pretrained(
    _TOKENIZER_MODEL,
    trust_remote_code=True,
)
# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def count_tokens(text: str) -> int:
    """
    Count the number of tokens in a text string using the Jina v3 tokenizer.
    Args:
        text: Any string of text.
    Returns:
        Integer token count. Special tokens (e.g. [CLS]) are excluded
        so the count reflects the "content" tokens only.
    Example:
        >>> count_tokens("Hello world")
        3
    """
    token_ids = _tokenizer.encode(text, add_special_tokens=False)
    return len(token_ids)
def chunk_document(
    text: str,
    document_id: str,
    chunk_size: int = 512,
    chunk_overlap: int = 100,
) -> list[dict]:
    """
    Split a document string into overlapping, paragraph-aware chunks.
    How splitting works:
        1. Try to split at paragraph boundaries (double newline: \\n\\n)
        2. If a paragraph is still too big, split at single newlines (\\n)
        3. If still too big, split at sentence ends (". ")
        4. Last resort: split at spaces
        This means the chunker NEVER breaks a paragraph unless forced to
        by size constraints — it always prefers natural boundaries.
    Overlap:
        The last `chunk_overlap` tokens of chunk N are repeated at the
        start of chunk N+1. This prevents information loss at boundaries.
    Args:
        text:         Full document text (all pages combined into one string).
        document_id:  Identifier for the source document (e.g. filename).
                      Stored in every chunk for later source tracing.
        chunk_size:   Maximum number of tokens per chunk. Default: 512.
        chunk_overlap: Number of tokens to overlap between chunks. Default: 100.
    Returns:
        List of chunk dicts. Empty list if text is empty.
        Each dict:
            {
                "chunk_index":  int   — 0-based position of this chunk
                "text":         str   — the actual chunk text
                "token_count":  int   — token count for this chunk's text
                "document_id":  str   — the document_id passed in
            }
    Example:
        >>> chunks = chunk_document("Long document...", document_id="report.pdf")
        >>> chunks[0]
        {"chunk_index": 0, "text": "...", "token_count": 487, "document_id": "report.pdf"}
    """
    # Guard: return empty list for empty text — never crash.
    if not text or not text.strip():
        return []
    # Build the splitter.
    # length_function=count_tokens ensures chunk_size refers to Jina tokens,
    # not characters. separators are tried in order — \\n\\n first (paragraphs).
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=count_tokens,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    raw_chunks: list[str] = splitter.split_text(text)
    # Build structured chunk objects with metadata.
    chunks: list[dict] = []
    for index, chunk_text in enumerate(raw_chunks):
        chunks.append({
            "chunk_index": index,
            "text": chunk_text,
            "token_count": count_tokens(chunk_text),
            "document_id": document_id,
        })
    return chunks
Step 3: Run tests — verify they ALL pass

bash
pytest tests/documentIngestion/chunking/test_recursive.py -v
Expected output:

PASSED tests/documentIngestion/test_chunker.py::TestCountTokens::test_returns_integer
PASSED tests/documentIngestion/test_chunker.py::TestCountTokens::test_empty_string
PASSED tests/documentIngestion/test_chunker.py::TestCountTokens::test_longer_text_has_more_tokens
PASSED tests/documentIngestion/test_chunker.py::TestCountTokens::test_token_count_is_reasonable
PASSED tests/documentIngestion/test_chunker.py::TestChunkDocument::test_returns_list
PASSED tests/documentIngestion/test_chunker.py::TestChunkDocument::test_each_item_is_dict
PASSED tests/documentIngestion/test_chunker.py::TestChunkDocument::test_required_keys_present
PASSED tests/documentIngestion/test_chunker.py::TestChunkDocument::test_chunk_index_sequential
PASSED tests/documentIngestion/test_chunker.py::TestChunkDocument::test_document_id_propagated
PASSED tests/documentIngestion/test_chunker.py::TestChunkDocument::test_no_chunk_exceeds_max_tokens
PASSED tests/documentIngestion/test_chunker.py::TestChunkDocument::test_token_count_matches_text
PASSED tests/documentIngestion/test_chunker.py::TestChunkDocument::test_multiple_chunks_produced_for_long_text
PASSED tests/documentIngestion/test_chunker.py::TestChunkDocument::test_short_text_produces_one_chunk
PASSED tests/documentIngestion/test_chunker.py::TestChunkDocument::test_custom_chunk_size
PASSED tests/documentIngestion/test_chunker.py::TestChunkDocument::test_text_is_not_empty_string
PASSED tests/documentIngestion/test_chunker.py::TestChunkDocument::test_empty_document_returns_empty_list
Step 4: Commit

bash
git add src/documentIngestion/chunking/ tests/
git commit -m "feat: add paragraph-aware token-counted chunker with Jina v3 tokenizer"
Task 4: Smoke Test With Real Text
This is NOT an automated test — it is a manual sanity check to see the chunker working on real text.

Step 1: Run this one-off script from the project root

bash
python3 -c "
from src.documentIngestion.chunking import chunk_document, count_tokens
# Simulate 3 pages of text merged together (Option B)
page1 = 'This is the first page content. ' * 40
page2 = 'This is the second page content. ' * 40
page3 = 'This is the third page content. ' * 40
full_text = page1 + '\n\n' + page2 + '\n\n' + page3
chunks = chunk_document(full_text, document_id='test_doc.pdf')
print(f'Total chunks: {len(chunks)}')
for c in chunks:
    print(f'  Chunk {c[\"chunk_index\"]}: {c[\"token_count\"]} tokens')
"
Expected output (approximate):

Total chunks: 3       ← or more, depending on text
  Chunk 0: 512 tokens
  Chunk 1: 512 tokens
  Chunk 2: ~300 tokens   ← last chunk may be smaller
What Is NOT In This Plan (Comes Next)
Step	What	File
Next	Context generation (LLM generates short summary per chunk)	chunker.py or separate contextualizer.py
After	Embedding (send chunk to Jina API)	embedder.py
After	Vector storage	vectorStore.py
After	Retrieval	retrieve.py
After	Pipeline orchestration	ingestion.py
Key Design Decisions (Explained)
Why RecursiveCharacterTextSplitter and not raw Python string splitting?
Writing your own splitter that handles paragraph → line → sentence → word fallback correctly is 200+ lines of tricky code. LangChain already solved this problem correctly. langchain-text-splitters is a lightweight package (no heavy LangChain dependencies) — it is the right tool for this specific job.

Why load the tokenizer once at module level?
AutoTokenizer.from_pretrained() downloads/loads model files from disk. It takes ~1-2 seconds. If you called it inside count_tokens(), it would reload every single time you counted tokens in a chunk — potentially 1000x slowdown. Loading once at module level means it loads once and is reused.

Why add_special_tokens=False in count_tokens()?
HuggingFace tokenizers automatically add [CLS] and [SEP] tokens. These are model-specific markers, not content. If you count them, chunk 1 might say it has 514 tokens when it only has 512 content tokens — and you'd set a limit of 512 but the chunk would actually overflow when embedded. Excluding special tokens gives you clean content-only counts.

Why document_id in every chunk?
During retrieval, when you find chunk 47, you need to know "which document did this come from?" so you can show the user a source citation. Without document_id, retrieved chunks are orphaned — you don't know where they came from.