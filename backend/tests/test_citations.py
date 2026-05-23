"""Citation parsing: mapping the model's [n] markers back to sources."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.services.citations import (
    build_citations,
    citation_to_dict,
    parse_cited_markers,
)


def _retrieved(filename: str, content: str, score: float, page: int | None = None):
    doc_id = uuid.uuid4()
    chunk = SimpleNamespace(
        id=uuid.uuid4(),
        document_id=doc_id,
        document=SimpleNamespace(filename=filename),
        page=page,
        char_start=0,
        char_end=len(content),
        content=content,
    )
    return SimpleNamespace(chunk=chunk, score=score)


def test_parse_markers_dedups_and_handles_adjacency():
    assert parse_cited_markers("Yes [1]. Also [3][3] and [10].") == {1, 3, 10}


def test_parse_markers_empty_when_none_present():
    assert parse_cited_markers("no citations here") == set()


def test_build_citations_flags_only_referenced_sources():
    contexts = [
        _retrieved("a.pdf", "alpha", 0.91, page=2),
        _retrieved("b.pdf", "bravo", 0.80),
        _retrieved("c.pdf", "charlie", 0.75),
    ]
    answer = "The answer relies on source [1] and source [3]."
    citations = build_citations(answer, contexts)

    assert [c.marker for c in citations] == [1, 2, 3]
    assert [c.cited for c in citations] == [True, False, True]
    assert citations[0].page == 2
    assert citations[0].filename == "a.pdf"


def test_citation_to_dict_is_json_safe():
    [c] = build_citations("uses [1]", [_retrieved("a.pdf", "alpha", 0.9)])
    d = citation_to_dict(c)
    assert isinstance(d["document_id"], str)
    assert isinstance(d["chunk_id"], str)
    assert d["cited"] is True
    assert d["score"] == 0.9
