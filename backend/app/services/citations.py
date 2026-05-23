"""Map the model's ``[n]`` markers back to real document locations.

The answer cites sources by the numbers we assigned in the prompt. Here we
parse those markers and resolve each one to the originating chunk — document,
page, character span and similarity score — so the UI can show *where* every
claim came from.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from app.services.vector_store import Retrieved

_MARKER_RE = re.compile(r"\[(\d+)\]")


@dataclass
class Citation:
    marker: int  # the [n] shown in the answer (1-based)
    cited: bool  # did the answer actually reference this source?
    document_id: uuid.UUID
    filename: str
    chunk_id: uuid.UUID
    page: int | None
    char_start: int
    char_end: int
    score: float
    content: str


def citation_to_dict(c: Citation) -> dict:
    """JSON-serialisable form (UUIDs → str) for API responses and the cache."""
    return {
        "marker": c.marker,
        "cited": c.cited,
        "document_id": str(c.document_id),
        "filename": c.filename,
        "chunk_id": str(c.chunk_id),
        "page": c.page,
        "char_start": c.char_start,
        "char_end": c.char_end,
        "score": c.score,
        "content": c.content,
    }


def parse_cited_markers(answer: str) -> set[int]:
    return {int(m) for m in _MARKER_RE.findall(answer)}


def build_citations(answer: str, contexts: list[Retrieved]) -> list[Citation]:
    """Build the source list for the numbered contexts, flagging cited ones."""
    used = parse_cited_markers(answer)
    citations: list[Citation] = []
    for i, r in enumerate(contexts, start=1):
        citations.append(
            Citation(
                marker=i,
                cited=i in used,
                document_id=r.chunk.document_id,
                filename=r.chunk.document.filename,
                chunk_id=r.chunk.id,
                page=r.chunk.page,
                char_start=r.chunk.char_start,
                char_end=r.chunk.char_end,
                score=round(r.score, 4),
                content=r.chunk.content,
            )
        )
    return citations
