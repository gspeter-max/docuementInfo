"""
Document parsing using the LlamaCloud SDK (llama-cloud >= 1.0).

Uploads a file to LlamaCloud and returns structured JSON page data via the
'items' expand option, which gives granular headings/paragraphs/tables
per page — more informative than plain markdown.
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

    # Step 1: Upload the file
    with open(file_path, "rb") as f:
        upload = client.files.upload(
            file=(file_path, f),
        )

    # Step 2: Parse it — request both text and structured JSON items
    result = client.parsing.parse(
        file_id=upload.id,
        tier="cost_effective",
        version="latest",
        expand=["text", "items"],
    )

    # Step 3: Normalise into list[dict] — one entry per page
    pages = []
    items_by_page: dict[int, list] = {}

    # Group items by their page number
    if result.items:
        for item in result.items:
            page_num = getattr(item, "page", 1)
            items_by_page.setdefault(page_num, []).append(item)

    # Build text per page from result.text (split by page marker) as fallback
    text_pages = []
    if result.text:
        # LlamaCloud puts a form-feed (\f) between pages
        text_pages = result.text.split("\f")

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
