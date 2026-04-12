import re

with open("docs/superpowers/plans/2026-04-12-strict-graph-ingestion.md", "r") as f:
    plan = f.read()

# 1. Update "New files to create" list in File Structure section
new_files_addition = """- `src/documentIngestion/prompts/graph/extraction_system.txt`
  - The system prompt instructions for graph extraction.
- `src/documentIngestion/prompts/graph/extraction_user.txt`
  - The user prompt template for graph extraction.
- `src/documentIngestion/prompts/graph/resolution_system.txt`
  - The system prompt instructions for entity resolution.
- `src/documentIngestion/prompts/graph/resolution_user.txt`
  - The user prompt template for entity resolution.
"""
plan = plan.replace("- `src/documentIngestion/models/graphExtractionModels.py`", new_files_addition + "- `src/documentIngestion/models/graphExtractionModels.py`")

# 2. Update Task 2 to include creating prompt files
task2_files = """**Files:**
- Create: `src/documentIngestion/graphExtraction.py`
- Create: `src/documentIngestion/prompts/graph/extraction_system.txt`
- Create: `src/documentIngestion/prompts/graph/extraction_user.txt`
- Modify: `src/providers/llmProvider.py`"""
plan = plan.replace("**Files:**\n- Create: `src/documentIngestion/graphExtraction.py`\n- Modify: `src/providers/llmProvider.py`", task2_files)


task2_prompt_builder_old = """```python
def build_graph_extraction_messages(chunk: dict[str, Any]) -> list[dict[str, str]]:
    \"\"\"This function puts together the instructions and the text piece so we can ask the AI to find names and connections.\"\"\"
    return [
        {
            "role": "system",
            "content": (
                "Extract entities and relationships from the chunk. "
                "Entity names and entity types are open-ended. "
                "Relationship types must be chosen only from this schema:\\n"
                f"{get_relationship_schema_prompt_text()}"
            ),
        },
        {
            "role": "user",
            "content": (
                f"Chunk id: {chunk['chunk_id']}\\n"
                f"Chunk text:\\n{chunk['text']}\\n\\n"
                "Return JSON with keys `entities` and `relationships`."
            ),
        },
    ]
```"""

task2_prompt_builder_new = """- [ ] **Step 4: Create prompt files and the prompt builder using them**

Create `src/documentIngestion/prompts/graph/extraction_system.txt`:
```txt
Extract entities and relationships from the chunk. Entity names and entity types are open-ended. Relationship types must be chosen only from this schema:
{schema_text}
```

Create `src/documentIngestion/prompts/graph/extraction_user.txt`:
```txt
Chunk id: {chunk_id}
Chunk text:
{chunk_text}

Return JSON with keys `entities` and `relationships`.
```

```python
from pathlib import Path

def build_graph_extraction_messages(chunk: dict[str, Any]) -> list[dict[str, str]]:
    \"\"\"This function puts together the instructions and the text piece so we can ask the AI to find names and connections.\"\"\"
    prompts_dir = Path(__file__).parent / "prompts" / "graph"
    system_prompt_template = (prompts_dir / "extraction_system.txt").read_text(encoding="utf-8")
    user_prompt_template = (prompts_dir / "extraction_user.txt").read_text(encoding="utf-8")

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
```"""

plan = plan.replace("- [ ] **Step 4: Add the prompt builder with the relationship schema text**\n\n" + task2_prompt_builder_old, task2_prompt_builder_new)
plan = plan.replace('git commit -m "feat: add strict graph extraction per chunk"', 'git add src/documentIngestion/prompts/graph\ngit commit -m "feat: add strict graph extraction per chunk"')

# 3. Update Task 4 to include creating prompt files
task4_files = """**Files:**
- Create: `src/documentIngestion/prompts/graph/resolution_system.txt`
- Create: `src/documentIngestion/prompts/graph/resolution_user.txt`
- Modify: `src/documentIngestion/models/graphExtractionModels.py`"""
plan = plan.replace("**Files:**\n- Modify: `src/documentIngestion/models/graphExtractionModels.py`", task4_files)

task4_prompt_builder_old = """```python
async def resolve_ambiguous_entity_pairs(
    *,
    llm_client: AsyncOpenAI,
    ambiguous_pairs: list[tuple[str, str, float]],
    model: str = DEFAULT_MODEL,
) -> list[EntityResolutionDecision]:
    \"\"\"This function asks the AI to look at pairs of names we are confused about, and decide if they are the same thing or different things.\"\"\"
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
```"""

task4_prompt_builder_new = """- [ ] **Step 4: Create prompt files and implement the focused cleanup prompt and parser**

Create `src/documentIngestion/prompts/graph/resolution_system.txt`:
```txt
You are an expert entity resolution system. Look at pairs of entity names and decide if they refer to the exact same real-world thing.
```

Create `src/documentIngestion/prompts/graph/resolution_user.txt`:
```txt
Here are the pairs of names to review:
{payload_json}

Return JSON with a `decisions` array.
```

```python
from pathlib import Path
import json

def build_entity_resolution_messages(payload: dict[str, Any]) -> list[dict[str, str]]:
    \"\"\"This function gets the right files with instructions to ask the AI if two names are the same.\"\"\"
    prompts_dir = Path(__file__).parent / "prompts" / "graph"
    system_prompt = (prompts_dir / "resolution_system.txt").read_text(encoding="utf-8")
    user_prompt_template = (prompts_dir / "resolution_user.txt").read_text(encoding="utf-8")

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
    \"\"\"This function asks the AI to look at pairs of names we are confused about, and decide if they are the same thing or different things.\"\"\"
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
```"""

plan = plan.replace("- [ ] **Step 4: Implement the focused cleanup prompt and parser**\n\n" + task4_prompt_builder_old, task4_prompt_builder_new)
plan = plan.replace('git commit -m "feat: add llm cleanup for ambiguous entity names"', 'git add src/documentIngestion/prompts/graph\ngit commit -m "feat: add llm cleanup for ambiguous entity names"')

with open("docs/superpowers/plans/2026-04-12-strict-graph-ingestion.md", "w") as f:
    f.write(plan)
