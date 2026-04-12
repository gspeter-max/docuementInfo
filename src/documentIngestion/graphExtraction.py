import json
from typing import Any
from pathlib import Path
from openai import AsyncOpenAI

from src.documentIngestion.graphRelationshipSchema import get_relationship_schema_prompt_text
from src.documentIngestion.models.graphExtractionModels import ChunkGraphExtractionResult
from src.providers.llmProvider import DEFAULT_MODEL


def parse_chunk_graph_extraction_response(response_payload: dict[str, Any]) -> ChunkGraphExtractionResult:
    """This checks if we can correctly understand the answer the AI gives us and pull out the names and connections from it."""
    return ChunkGraphExtractionResult(**response_payload)


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
