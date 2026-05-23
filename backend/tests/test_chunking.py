"""Chunking: overlap, offset tracking, and page stamping."""

from __future__ import annotations

from app.core.config import settings
from app.services.chunking import chunk_document
from app.services.extraction import ExtractedDoc, PageSpan

# Varied (non-repetitive) text — comfortably larger than one chunk. Distinct
# sentences matter: the splitter locates each chunk's offset by substring
# search, which is ambiguous if the text repeats itself verbatim.
_TEXT = " ".join(
    f"Sentence {i} discusses retrieval topic {i} and explains concept {i} "
    f"with enough distinct words to occupy meaningful space in the document."
    for i in range(1, 90)
)


def _doc() -> ExtractedDoc:
    return ExtractedDoc(text=_TEXT, page_spans=[PageSpan(0, len(_TEXT), None)])


def test_produces_multiple_chunks():
    chunks = chunk_document(_doc())
    assert len(chunks) > 1


def test_chunks_respect_max_size_with_slack():
    # RecursiveCharacterTextSplitter targets chunk_size but may slightly exceed
    # it when no separator is available; allow a small margin.
    chunks = chunk_document(_doc())
    assert all(len(c.content) <= settings.chunk_size * 1.2 for c in chunks)


def test_offsets_are_within_bounds_and_ordered():
    chunks = chunk_document(_doc())
    assert chunks[0].char_start == 0
    for c in chunks:
        assert 0 <= c.char_start < c.char_end <= len(_TEXT)
    starts = [c.char_start for c in chunks]
    assert starts == sorted(starts)


def test_consecutive_chunks_overlap():
    chunks = chunk_document(_doc())
    # With CHUNK_OVERLAP > 0, at least one neighbour pair must overlap.
    assert any(
        nxt.char_start < cur.char_end for cur, nxt in zip(chunks, chunks[1:], strict=False)
    )


def test_page_is_stamped_from_offset_map():
    page1 = "First page intro text.\n\n"
    page2 = " ".join(f"Detail point {i} on the second page." for i in range(1, 80))
    text = page1 + page2
    spans = [PageSpan(0, len(page1), 1), PageSpan(len(page1), len(text), 2)]
    chunks = chunk_document(ExtractedDoc(text=text, page_spans=spans))
    assert chunks[0].page == 1
    assert chunks[-1].page == 2
