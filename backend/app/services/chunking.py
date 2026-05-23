"""Chunking.

We use LangChain's ``RecursiveCharacterTextSplitter``, which tries a hierarchy
of separators (paragraph → line → sentence → word) and only falls back to a
hard cut when a single unit is larger than the target. So we get *semantic*
boundaries, not blind fixed-width slices that decapitate sentences.

Why these defaults (override via env):

* ``CHUNK_SIZE=1000`` chars ≈ 200–250 tokens. That sits well inside the
  embedding model's window and keeps each chunk topically focused, so a
  retrieved chunk is mostly signal rather than a wall of mixed context.
* ``CHUNK_OVERLAP=150`` (~15%) carries a sentence or two across each boundary,
  so a fact that straddles two chunks is still findable from either side.

``add_start_index=True`` gives us each chunk's character offset for free, which
we combine with the page map to produce real citations.
"""

from __future__ import annotations

from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import settings
from app.services.extraction import ExtractedDoc


@dataclass
class TextChunk:
    index: int
    content: str
    char_start: int
    char_end: int
    page: int | None


def _build_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        add_start_index=True,
        separators=["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ", ""],
    )


def chunk_document(doc: ExtractedDoc) -> list[TextChunk]:
    """Split an extracted document into overlapping, page-aware chunks."""
    splitter = _build_splitter()
    pieces = splitter.create_documents([doc.text])

    chunks: list[TextChunk] = []
    for i, piece in enumerate(pieces):
        content = piece.page_content.strip()
        if not content:
            continue
        start = int(piece.metadata.get("start_index", 0))
        end = start + len(piece.page_content)
        chunks.append(
            TextChunk(
                index=i,
                content=content,
                char_start=start,
                char_end=end,
                page=doc.page_at(start),
            )
        )
    return chunks
