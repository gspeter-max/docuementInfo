# Prompt Files Cleanup And Python Migration Plan

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the four prompt markdown files with two simple Python files. One Python file should hold both extraction prompts. One Python file should hold both name-check prompts. The prompt text should also be improved, but the current behavior must stay the same.

**Why This Change:** Right now a developer has to jump across four markdown files to understand two prompt flows. That slows down reading and makes the repo harder to scan. Putting each prompt pair into one Python file makes the structure easier to understand:
- one file for extraction work
- one file for checking if two names are the same

**Architecture:** Delete these four markdown files:
- `src/documentIngestion/prompts/graph/extraction_system.md`
- `src/documentIngestion/prompts/graph/extraction_user.md`
- `src/documentIngestion/prompts/graph/resolution_system.md`
- `src/documentIngestion/prompts/graph/resolution_user.md`

Create these two Python files:
- `src/documentIngestion/prompts/graph/prompts_for_extracting_graph_data.py`
- `src/documentIngestion/prompts/graph/prompts_for_checking_if_two_names_are_the_same.py`

Each Python file should contain both prompt constants for its task:
- `SYSTEM_PROMPT`
- `USER_PROMPT_TEMPLATE`

The filenames should say the job in plain English so a new developer can understand them quickly without opening other files.

**Tech Stack:** Python, OpenAI JSON Mode.

---

### Task 1: Move the extraction prompts into one Python file

**Files:**
- Delete: `src/documentIngestion/prompts/graph/extraction_system.md`
- Delete: `src/documentIngestion/prompts/graph/extraction_user.md`
- Create: `src/documentIngestion/prompts/graph/prompts_for_extracting_graph_data.py`
- Modify: `src/documentIngestion/graphExtraction.py`

**Step 1: Create the extraction prompt Python file**

Create `src/documentIngestion/prompts/graph/prompts_for_extracting_graph_data.py`.

This file should contain:
- `SYSTEM_PROMPT`
- `USER_PROMPT_TEMPLATE`

The prompt content should keep the current extraction behavior. Do not weaken the existing schema rules. Keep the instructions about:
- allowed relationship types
- not inventing new relationship types
- using `RELATED_TO` when needed
- keeping `evidence_text`
- returning the expected JSON structure

The current extraction system prompt uses `{schema_text}`. Keep that behavior in the Python file too, for example:

```python
SYSTEM_PROMPT = """... {schema_text} ..."""

USER_PROMPT_TEMPLATE = """..."""
```

**Step 2: Update `src/documentIngestion/graphExtraction.py`**

Stop reading the markdown files with `Path(...).read_text(...)`.

Import both constants from the new file:

```python
from src.documentIngestion.prompts.graph.prompts_for_extracting_graph_data import (
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
)
```

Then build the messages using:

```python
SYSTEM_PROMPT.format(schema_text=get_relationship_schema_prompt_text())
USER_PROMPT_TEMPLATE.format(...)
```

**Step 3: Keep the prompt wording clear**

Improve readability where useful, but do not remove the current extraction requirements or examples unless there is a strong reason.

**Step 4: Commit**

```bash
git add src/documentIngestion/prompts/graph/prompts_for_extracting_graph_data.py
git add src/documentIngestion/graphExtraction.py
git commit -m "refactor: move extraction prompts into one python file"
```

---

### Task 2: Move the name-check prompts into one Python file

**Files:**
- Delete: `src/documentIngestion/prompts/graph/resolution_system.md`
- Delete: `src/documentIngestion/prompts/graph/resolution_user.md`
- Create: `src/documentIngestion/prompts/graph/prompts_for_checking_if_two_names_are_the_same.py`
- Modify: `src/documentIngestion/entityResolution.py`

**Step 1: Create the name-check prompt Python file**

Create `src/documentIngestion/prompts/graph/prompts_for_checking_if_two_names_are_the_same.py`.

This file should contain:
- `SYSTEM_PROMPT`
- `USER_PROMPT_TEMPLATE`

The system prompt should keep the same job as the current resolution prompt:
- decide whether two names refer to the same real-world thing
- merge only when confidence is high
- set `canonical_name` only for true merges
- keep `canonical_name` empty for false or uncertain cases
- return only JSON with a `decisions` array

The wording should be improved so both the model and the developer can understand it faster.

Suggested shape:

```python
SYSTEM_PROMPT = """Look at pairs of names and decide whether they refer to the same real-world thing, such as a person, company, or place.

Merge only when you are completely confident they are the same thing. If the names differ only in small formatting changes, punctuation changes, abbreviations, or common naming variations, treat them as the same only when that is clearly correct.

If two names are the same:
- set `should_merge` to true
- set `canonical_name` to the best, most complete, and most correct version of the name

If two names are not the same, or you are not sure:
- set `should_merge` to false
- leave `canonical_name` empty

Return only a JSON object with a `decisions` array.
Each item in `decisions` must look like this:
{
  "left_name": "...",
  "right_name": "...",
  "should_merge": true or false,
  "canonical_name": "..."
}"""

USER_PROMPT_TEMPLATE = """Here are the name pairs to check.

{payload_json}

Return only a JSON object with a `decisions` array."""
```

**Step 2: Update `src/documentIngestion/entityResolution.py`**

Stop reading the markdown files with `Path(...).read_text(...)`.

Import both constants from the new file:

```python
from src.documentIngestion.prompts.graph.prompts_for_checking_if_two_names_are_the_same import (
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
)
```

Then build the messages from those imported constants.

**Step 3: Commit**

```bash
git add src/documentIngestion/prompts/graph/prompts_for_checking_if_two_names_are_the_same.py
git add src/documentIngestion/entityResolution.py
git commit -m "refactor: move name-check prompts into one python file"
```

---

### Task 3: Update tests to match the new Python prompt files

**Files:**
- Modify: `tests/documentIngestion/test_prompt_contracts.py`

**Step 1: Update the extraction prompt contract tests**

Change the extraction tests so they import `SYSTEM_PROMPT` and `USER_PROMPT_TEMPLATE` from:

```python
src.documentIngestion.prompts.graph.prompts_for_extracting_graph_data
```

Keep the same assertions for:
- `RELATED_TO`
- `Never invent a new relationship type`
- `evidence_text`
- the expected JSON keys
- the one-shot example in the user prompt

When the extraction system prompt contains `{schema_text}`, format it in the test before asserting on the final text.

**Step 2: Update the name-check prompt contract test**

Change the name-check test so it imports `SYSTEM_PROMPT` from:

```python
src.documentIngestion.prompts.graph.prompts_for_checking_if_two_names_are_the_same
```

Keep the same assertions for:
- `decisions`
- `canonical_name`

**Step 3: Run tests**

```bash
pytest tests/documentIngestion/test_prompt_contracts.py -v
```

**Step 4: Commit**

```bash
git add tests/documentIngestion/test_prompt_contracts.py
git commit -m "test: update prompt contract tests for python prompt files"
```

---

### Task 4: Add package markers only if imports need them

**Files:**
- Maybe create: `src/documentIngestion/prompts/__init__.py`
- Maybe create: `src/documentIngestion/prompts/graph/__init__.py`

**Step 1: Check imports**

If the new prompt files import cleanly without package marker files, do nothing.

**Step 2: Add the smallest fix if needed**

Create empty `__init__.py` files only if the import path requires them.

---

### Appendix: Exact Direction Of The Change

**Old structure:**
- `extraction_system.md`
- `extraction_user.md`
- `resolution_system.md`
- `resolution_user.md`

**New structure:**
- `prompts_for_extracting_graph_data.py`
- `prompts_for_checking_if_two_names_are_the_same.py`

**Prompt constants in each new file:**
- `SYSTEM_PROMPT`
- `USER_PROMPT_TEMPLATE`

**Important behavior to preserve:**
- Extraction must still follow the current graph schema rules.
- Extraction must still keep `RELATED_TO` and `evidence_text` behavior.
- Name checking must still return strict JSON with `decisions`.
- Name checking must still use `canonical_name`.
- Low-confidence name pairs must still avoid merging.
