"""
LLM Grader.

Analyzes retrieved chunks for a specific query and determines if they contain
sufficient information to answer the query. If insufficient, provides a reason
to justify graph escalation.
"""
import json
import structlog
from pydantic import BaseModel, Field

from providers.llmProvider import build_mistral_client, DEFAULT_MODEL

log = structlog.get_logger()


class GraderResult(BaseModel):
    sufficient: bool = Field(description="True if the chunks contain enough info to answer the query, False otherwise.")
    reason: str = Field(description="Reason why it is sufficient or insufficient.")


GRADER_PROMPT = """
You are a grader for a Retrieval-Augmented Generation (RAG) system.
Your job is to determine if the provided retrieved documents contain sufficient information to fully answer the user's query.

CRITERIA:
- sufficient=True: The query can be fully answered based ONLY on the provided chunks.
- sufficient=False: The query cannot be fully answered because info is missing, incomplete, or unrelated.

OUTPUT FORMAT:
You MUST return your answer as a JSON object with exactly two keys: "sufficient" (boolean) and "reason" (string explaining why).

Example Output:
{
    "sufficient": false,
    "reason": "The documents mention John Doe but do not state who he reports to."
}
"""


async def grade_chunks(query: str, chunks: list[str]) -> GraderResult:
    """
    Grades whether the provided chunks are sufficient to answer the query.
    If JSON parsing fails, defaults to sufficient=False to err on the side of safety (escalation).
    """
    if not chunks:
        return GraderResult(sufficient=False, reason="No chunks provided.")

    try:
        client = await build_mistral_client()

        # Combine chunks into a single text block
        chunks_text = "\n\n---\n\n".join(chunks)

        user_content = f"QUERY: {query}\n\nRETRIEVED DOCUMENTS:\n{chunks_text}"

        response = await client.chat.completions.create(
            model=DEFAULT_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": GRADER_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.0,
        )

        content = response.choices[0].message.content
        if not content:
            log.warning("Grader received empty response from LLM, defaulting to insufficient")
            return GraderResult(sufficient=False, reason="Empty LLM response.")

        data = json.loads(content)
        result = GraderResult(
            sufficient=bool(data.get("sufficient", False)),
            reason=str(data.get("reason", "No reason provided by LLM."))
        )

        if not result.sufficient:
            log.info("Grader deemed chunks insufficient", reason=result.reason)

        return result

    except Exception as e:
        log.error("Grader LLM call failed, defaulting to insufficient", error=str(e))
        return GraderResult(sufficient=False, reason=f"Grader error: {str(e)}")
