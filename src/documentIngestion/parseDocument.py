"""
Document parsing using the LlamaCloud SDK (llama-cloud >= 2.0).

Uses the single-call parsing.parse() API that accepts upload_file directly,
so no separate file upload step is needed. Returns structured JSON page data
via the 'items' expand option (headings, paragraphs, tables per page).
"""
from llama_cloud import LlamaCloud
from config import llama_parse_api_key


def _build_client() -> LlamaCloud:
    """Initialise the LlamaCloud client using the API key from config."""
    return LlamaCloud(api_key=llama_parse_api_key)


def parse_document(file_path: str) -> list[dict]:
    """
    Parse a document via LlamaCloud and return a normalised list of page dicts.

    Each dict in the returned list contains:
        "page"   → 1-based page number (int)
        "text"   → plain text for that page (str)
        "items"  → structured JSON list of blocks (headings, paragraphs, tables)

    Args:
        file_path: Absolute or relative path to the document (PDF, DOCX, …).

    Returns:
        A list of page dicts.
    """
    client = _build_client()

    # Single-call: upload + parse + poll in one step using upload_file=
    with open(file_path, "rb") as f:
        result = client.parsing.parse(
            upload_file=(file_path, f),
            tier="cost_effective",
            version="latest",
            expand=["text", "items"],
        )

    # Group items by their page number
    items_by_page: dict[int, list] = {}
    if result.items:
        for item in result.items:
            page_num = getattr(item, "page", 1)
            items_by_page.setdefault(page_num, []).append(item)

    # Split full text into per-page chunks (LlamaCloud separates pages with \f)
    text_pages: list[str] = []
    if result.text:
        text_pages = result.text.split("\f")

    pages = []
    for i, text in enumerate(text_pages, start=1):
        pages.append({
            "page": i,
            "text": text.strip(),
            "items": items_by_page.get(i, []),
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
