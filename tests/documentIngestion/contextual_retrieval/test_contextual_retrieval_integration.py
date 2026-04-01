import pytest
import respx
from httpx import Response

from src.config import lightning_api_key
from src.documentIngestion.contextual_retrieval import (
    build_contextualized_document,
    build_lightning_client,
    generate_chunk_context,
)


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
