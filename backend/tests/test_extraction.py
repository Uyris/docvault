"""Text extraction + the page-offset map that powers citations."""

from __future__ import annotations

import pytest
from app.services.extraction import (
    ExtractedDoc,
    ExtractionError,
    PageSpan,
    extract_text,
)


def test_extract_plain_text():
    doc = extract_text("notes.txt", "text/plain", b"hello world")
    assert doc.text == "hello world"
    assert doc.page_at(0) is None  # plain text has no page


def test_extract_markdown():
    doc = extract_text("readme.md", "text/markdown", b"# Title\n\nbody")
    assert "Title" in doc.text


def test_empty_file_raises():
    with pytest.raises(ExtractionError):
        extract_text("empty.txt", "text/plain", b"   ")


def test_page_at_resolves_offset_to_page():
    doc = ExtractedDoc(
        text="a" * 30,
        page_spans=[PageSpan(0, 10, 1), PageSpan(10, 20, 2), PageSpan(20, 30, 3)],
    )
    assert doc.page_at(5) == 1
    assert doc.page_at(15) == 2
    assert doc.page_at(25) == 3
    # Past the end clamps to the last known page.
    assert doc.page_at(999) == 3
