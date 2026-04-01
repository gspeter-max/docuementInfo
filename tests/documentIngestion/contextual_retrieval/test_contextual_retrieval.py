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


def test_build_lightning_client_requires_key():
    try:
        build_lightning_client(api_key="")
        assert False, "Expected EnvironmentError"
    except EnvironmentError:
        assert True
