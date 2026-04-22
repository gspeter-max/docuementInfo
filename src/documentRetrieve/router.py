"""
LLM-based query intent router.

Takes a query string and uses Mistral's structured output (json_object)
to classify the intent as either "simple" or "complex".
No keywords or regex, pure LLM routing.
Defaults to "simple" on failure.
"""
import json
import structlog
from typing import Literal

from providers.llmProvider import build_mistral_client, DEFAULT_MODEL

log = structlog.get_logger()

IntentType = Literal["simple", "complex"]


ROUTER_PROMPT = """
You are an expert query classifier for a Retrieval-Augmented Generation (RAG) system.
Your job is to determine if a user query requires simple fact retrieval or complex relationship traversal.

CLASSIFICATION RULES:
- "simple": The query asks for facts, definitions, summaries, or specific details that are likely found in a single text passage.
- "complex": The query asks for connections, relationships, dependencies, hierarchies, or comparisons that span multiple entities (e.g., "How does X relate to Y?", "What teams does X manage?", "Dependencies of Y").

You MUST return your answer as a JSON object with exactly one key: "intent".
The value must be strictly either "simple" or "complex".

Example Output:
{
    "intent": "simple"
}
"""


async def classify_intent(query: str) -> IntentType:
    """
    Classifies a user query's intent as "simple" or "complex" using an LLM.

    Args:
        query: The user's query string.

    Returns:
        "simple" or "complex". Defaults to "simple" if parsing fails or LLM gives unexpected output.
    """
    try:
        client = await build_mistral_client()

        response = await client.chat.completions.create(
            model=DEFAULT_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": ROUTER_PROMPT},
                {"role": "user", "content": query},
            ],
            temperature=0.0,
        )

        content = response.choices[0].message.content
        if not content:
            log.warning("Router received empty response from LLM, defaulting to 'simple'")
            return "simple"

        data = json.loads(content)
        intent = data.get("intent", "").lower()

        if intent in ("simple", "complex"):
            return intent  # type: ignore

        log.warning("Router received unexpected intent, defaulting to 'simple'", parsed_intent=intent)
        return "simple"

    except Exception as e:
        log.error("Router LLM call failed, defaulting to 'simple'", error=str(e))
        return "simple"
