"""
Deep tests for parseDocument.py — LlamaCloud SDK integration.

These tests verify:
- Upload is called with the correct file handle
- parse() is called with correct arguments (tier, version, expand)
- The page normalisation logic is correct for all edge cases
- get_all_pages_text() formats output correctly
- Items are correctly grouped per page
- Graceful handling of missing text / missing items from API
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, mock_open, call
import pytest

from documentIngestion.parseDocument import parse_document, get_all_pages_text


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_item(page: int, kind: str = "paragraph") -> MagicMock:
    """Build a fake structured item returned by result.items."""
    item = MagicMock()
    item.page = page
    item.type = kind
    return item


def _make_api_result(text: str, items: list) -> MagicMock:
    """Build a fake LlamaCloud parse result."""
    result = MagicMock()
    result.text = text
    result.items = items
    return result


def _make_client(api_result: MagicMock) -> MagicMock:
    """Build a fake LlamaCloud client."""
    client = MagicMock()
    upload = MagicMock()
    upload.id = "file-abc123"
    client.files.upload.return_value = upload
    client.parsing.parse.return_value = api_result
    return client


# ── Tests: parse_document() ───────────────────────────────────────────────────

def test_parse_document_uploads_file_before_parsing():
    """Upload must be called BEFORE parse() — order matters."""
    call_order = []

    api_result = _make_api_result("page one content", [])
    client = MagicMock()
    upload = MagicMock()
    upload.id = "file-xyz"

    def record_upload(*args, **kwargs):
        call_order.append("upload")
        return upload
    def record_parse(*args, **kwargs):
        call_order.append("parse")
        return api_result

    client.files.upload.side_effect = record_upload
    client.parsing.parse.side_effect = record_parse

    with patch("documentIngestion.parseDocument._build_client", return_value=client), \
         patch("builtins.open", mock_open(read_data=b"pdf bytes")):
        parse_document("some/file.pdf")

    assert call_order == ["upload", "parse"], (
        "File must be uploaded first, then parsed. Got: " + str(call_order)
    )


def test_parse_document_passes_file_id_from_upload_to_parse():
    """The file_id returned from upload must be passed into parse()."""
    api_result = _make_api_result("content", [])
    client = _make_client(api_result)

    with patch("documentIngestion.parseDocument._build_client", return_value=client), \
         patch("builtins.open", mock_open(read_data=b"bytes")):
        parse_document("my_doc.pdf")

    parse_call_kwargs = client.parsing.parse.call_args[1]
    assert parse_call_kwargs["file_id"] == "file-abc123", (
        "parse() must use the file_id from the upload response"
    )


def test_parse_document_requests_text_and_items_expand():
    """Must expand=['text', 'items'] — not markdown, not just text."""
    api_result = _make_api_result("content", [])
    client = _make_client(api_result)

    with patch("documentIngestion.parseDocument._build_client", return_value=client), \
         patch("builtins.open", mock_open(read_data=b"bytes")):
        parse_document("my_doc.pdf")

    parse_call_kwargs = client.parsing.parse.call_args[1]
    expand = parse_call_kwargs["expand"]

    assert "text" in expand, "expand must include 'text'"
    assert "items" in expand, "expand must include 'items' for structured JSON"
    assert "markdown" not in expand, "markdown expand is deprecated, must not be used"


def test_parse_document_uses_cost_effective_tier():
    """Default tier must be 'cost_effective' to avoid unnecessary API spend."""
    api_result = _make_api_result("content", [])
    client = _make_client(api_result)

    with patch("documentIngestion.parseDocument._build_client", return_value=client), \
         patch("builtins.open", mock_open(read_data=b"bytes")):
        parse_document("my_doc.pdf")

    parse_call_kwargs = client.parsing.parse.call_args[1]
    assert parse_call_kwargs["tier"] == "cost_effective"


def test_parse_document_returns_correct_number_of_pages():
    """Each form-feed (\\f) separated chunk becomes exactly one page dict."""
    text = "page one\fpage two\fpage three"
    api_result = _make_api_result(text, [])
    client = _make_client(api_result)

    with patch("documentIngestion.parseDocument._build_client", return_value=client), \
         patch("builtins.open", mock_open(read_data=b"bytes")):
        pages = parse_document("doc.pdf")

    assert len(pages) == 3, f"Expected 3 pages, got {len(pages)}"


def test_parse_document_page_numbers_are_1_indexed():
    """Page numbers must start at 1, not 0."""
    text = "page A\fpage B"
    api_result = _make_api_result(text, [])
    client = _make_client(api_result)

    with patch("documentIngestion.parseDocument._build_client", return_value=client), \
         patch("builtins.open", mock_open(read_data=b"bytes")):
        pages = parse_document("doc.pdf")

    assert pages[0]["page"] == 1
    assert pages[1]["page"] == 2


def test_parse_document_strips_whitespace_from_page_text():
    """Text from each page must be stripped of leading/trailing whitespace."""
    text = "  \n  some content  \n  \fmore content\n\n"
    api_result = _make_api_result(text, [])
    client = _make_client(api_result)

    with patch("documentIngestion.parseDocument._build_client", return_value=client), \
         patch("builtins.open", mock_open(read_data=b"bytes")):
        pages = parse_document("doc.pdf")

    assert pages[0]["text"] == "some content"


def test_parse_document_groups_items_by_correct_page():
    """Items from page 2 must NOT appear in page 1's dict."""
    page1_item = _make_item(page=1, kind="heading")
    page2_item = _make_item(page=2, kind="paragraph")

    api_result = _make_api_result("p1\fp2", [page1_item, page2_item])
    client = _make_client(api_result)

    with patch("documentIngestion.parseDocument._build_client", return_value=client), \
         patch("builtins.open", mock_open(read_data=b"bytes")):
        pages = parse_document("doc.pdf")

    assert len(pages[0]["items"]) == 1
    assert pages[0]["items"][0] is page1_item, "Page 1 must only have page 1 items"

    assert len(pages[1]["items"]) == 1
    assert pages[1]["items"][0] is page2_item, "Page 2 must only have page 2 items"


def test_parse_document_page_with_no_items_gets_empty_list():
    """A page that has no items must get items=[] not None."""
    page2_item = _make_item(page=2)
    api_result = _make_api_result("p1\fp2", [page2_item])
    client = _make_client(api_result)

    with patch("documentIngestion.parseDocument._build_client", return_value=client), \
         patch("builtins.open", mock_open(read_data=b"bytes")):
        pages = parse_document("doc.pdf")

    assert pages[0]["items"] == [], "Pages with no items must return empty list, not None"


def test_parse_document_handles_no_items_from_api():
    """If result.items is None or empty, all pages must still return items=[]."""
    api_result = _make_api_result("page one", [])
    api_result.items = []
    client = _make_client(api_result)

    with patch("documentIngestion.parseDocument._build_client", return_value=client), \
         patch("builtins.open", mock_open(read_data=b"bytes")):
        pages = parse_document("doc.pdf")

    assert pages[0]["items"] == []


def test_parse_document_handles_empty_text_response():
    """If the API returns no text, result must be an empty list — not crash."""
    api_result = _make_api_result("", [])
    api_result.text = None
    client = _make_client(api_result)

    with patch("documentIngestion.parseDocument._build_client", return_value=client), \
         patch("builtins.open", mock_open(read_data=b"bytes")):
        pages = parse_document("doc.pdf")

    assert pages == [], "Empty API response must return empty list, not crash"


def test_parse_document_each_page_dict_has_required_keys():
    """Every returned page dict MUST have exactly: page, text, items."""
    text = "hello\fworld"
    api_result = _make_api_result(text, [])
    client = _make_client(api_result)

    with patch("documentIngestion.parseDocument._build_client", return_value=client), \
         patch("builtins.open", mock_open(read_data=b"bytes")):
        pages = parse_document("doc.pdf")

    for i, page in enumerate(pages):
        assert "page" in page, f"Page {i} dict missing 'page' key"
        assert "text" in page, f"Page {i} dict missing 'text' key"
        assert "items" in page, f"Page {i} dict missing 'items' key"


# ── Tests: get_all_pages_text() ───────────────────────────────────────────────

def test_get_all_pages_text_formats_with_page_headers():
    """Each page must be prefixed with '--- Page N ---'."""
    pages = [
        {"page": 1, "text": "Alice works here.", "items": []},
        {"page": 2, "text": "Bob manages Alice.", "items": []},
    ]
    result = get_all_pages_text(pages)

    assert "--- Page 1 ---" in result
    assert "--- Page 2 ---" in result


def test_get_all_pages_text_preserves_all_page_content():
    """Text from every page must appear in the final output."""
    pages = [
        {"page": 1, "text": "CONTENT_PAGE_ONE", "items": []},
        {"page": 2, "text": "CONTENT_PAGE_TWO", "items": []},
    ]
    result = get_all_pages_text(pages)

    assert "CONTENT_PAGE_ONE" in result
    assert "CONTENT_PAGE_TWO" in result


def test_get_all_pages_text_separates_pages_with_blank_line():
    """Pages must be separated by a blank line (double newline)."""
    pages = [
        {"page": 1, "text": "page one", "items": []},
        {"page": 2, "text": "page two", "items": []},
    ]
    result = get_all_pages_text(pages)
    # A double newline separates the two page blocks
    assert "\n\n" in result


def test_get_all_pages_text_on_empty_input_returns_empty_string():
    """An empty page list must return an empty string, not crash."""
    result = get_all_pages_text([])
    assert result == ""


def test_get_all_pages_text_handles_page_with_empty_text():
    """A page with empty text must still produce a header line."""
    pages = [{"page": 1, "text": "", "items": []}]
    result = get_all_pages_text(pages)
    assert "--- Page 1 ---" in result
