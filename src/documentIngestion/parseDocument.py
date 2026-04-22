"""
Document parsing using the LlamaCloud SDK (llama-cloud >= 1.0).

Uploads a file to LlamaCloud and returns parsed page text.
"""
from llama_cloud import LlamaCloud
from config import llama_parse_api_key


def _build_client() -> LlamaCloud:
    """Initialise the LlamaCloud client using the API key from config."""
    return LlamaCloud(token=llama_parse_api_key)


def parse_document(file_path: str) -> list[dict]:
    """
    Parse a document via LlamaCloud and return a normalised list of page dicts.

    Each dict in the returned list contains:
        "page"  → 1-based page number (int)
        "text"  → extracted markdown text for that page (str)

    Args:
        file_path: Absolute or relative path to the document (PDF, DOCX, …).

    Returns:
        A list of page dicts.
    """
    client = _build_client()

    # Step 1: Upload the file
    with open(file_path, "rb") as f:
        upload = client.files.upload(
            file=(file_path, f),
        )

    # Step 2: Parse it
    result = client.parsing.parse(
        file_id=upload.id,
        tier="cost_effective",
        version="latest",
        expand=["markdown"],
    )

    # Step 3: Normalise into list[dict] matching the old interface
    pages = []
    for i, page in enumerate(result.markdown.pages, start=1):
        pages.append({
            "page": i,
            "text": page.markdown or "",
        })

    return pages


def get_all_pages_text(pages: list[dict]) -> str:
    """
    Concatenate all page texts from the output of parse_document().

    Args:
        pages: The list returned by parse_document().

    Returns:
        A single string with each page's text separated by a blank line,
        prefixed with a header marker:

            --- Page 1 ---
            <text>

            --- Page 2 ---
            <text>
    """
    page_texts: list[str] = []
    for page in pages:
        page_number = page.get("page", "?")
        text = page.get("text", "").strip()
        page_texts.append(f"--- Page {page_number} ---\n{text}")

    return "\n\n".join(page_texts)
