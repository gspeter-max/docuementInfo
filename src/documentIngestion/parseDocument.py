import os
import sys

# ---------------------------------------------------------------------------
# Make the project root (documentInFo/) visible to Python's import system.
#
# Why is this needed?
#   When you run:  python3 src/documentIngestion/parseDocument.py
#   Python only adds THIS file's folder (src/documentIngestion/) to sys.path.
#   It has no idea where "src" or "src.config" is.
#
# __file__  →  .../documentInFo/src/documentIngestion/parseDocument.py
# os.path.dirname(__file__)                   →  .../documentInFo/src/documentIngestion
# os.path.dirname(os.path.dirname(__file__))  →  .../documentInFo/src
# os.path.dirname(...dirname(...dirname(...))) →  .../documentInFo   ← PROJECT ROOT
# ---------------------------------------------------------------------------
# We insert the project root at position 0 (highest priority) so that
# "from src.config import ..." resolves to documentInFo/src/config.py
# ---------------------------------------------------------------------------
# _project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# if _project_root not in sys.path:
#     sys.path.insert(0, _project_root)

from llama_parse import LlamaParse
from src.config import llama_parse_api_key

def _build_parser() -> LlamaParse:
    """
    Initialise a LlamaParse instance from the environment.

    Expects:  LLAMA_PARSE_APIKEY  (set in your .env / shell)
    """

    return LlamaParse(
        api_key=llama_parse_api_key,
        result_type="markdown",   # "markdown" or "text"
        verbose=False,
        language="en",
    )



def parse_document(file_path: str) -> list[dict]:
    """
    Parse a document and return the raw JSON result from LlamaParse.

    Args:
        file_path: Absolute or relative path to the document
                   (PDF, DOCX, PPTX, …).

    Returns:
        A list of result dicts — one per file processed.
        Each dict contains:
            "pages"        → list of page objects
            "job_metadata" → credits used, total pages, etc.

        Each page object contains:
            "page"  → 1-based page number
            "text"  → raw extracted text for that page
            "md"    → markdown representation of that page
            "items" → granular list of headings / paragraphs / tables
    """
    parser = _build_parser()
    json_result: list[dict] = parser.get_json_result(file_path)
    return json_result


def get_all_pages_text(json_result: list[dict]) -> str:
    """
    Extract and concatenate the text from every page across all files
    in a JSON result returned by parse_document().

    Args:
        json_result: The list returned by parse_document().

    Returns:
        A single string with each page's text separated by a blank line.
        Page boundaries are marked with a header so callers can split
        back on them if needed:

            --- Page 1 ---
            <text>

            --- Page 2 ---
            <text>
            ...
    """
    page_texts: list[str] = []

    for file_result in json_result:
        pages: list[dict] = file_result.get("pages", [])
        for page in pages:
            page_number = page.get("page", "?")
            text = page.get("text", "").strip()
            page_texts.append(f"--- Page {page_number} ---\n{text}")

    return "\n\n".join(page_texts)
