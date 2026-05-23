"""Text extraction from uploaded files.

Returns the full document text *plus* a map from character offset to source
page. The chunker later uses that map to stamp each chunk with the page it came
from, which is what makes citations point at a real location instead of just
quoting text.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

from pypdf import PdfReader

from app.core.logging import get_logger

log = get_logger(__name__)


class ExtractionError(ValueError):
    """Raised when a file can't be parsed or contains no extractable text."""


@dataclass
class PageSpan:
    start: int
    end: int
    page: int | None


@dataclass
class ExtractedDoc:
    text: str
    page_spans: list[PageSpan] = field(default_factory=list)

    def page_at(self, offset: int) -> int | None:
        """Page number containing ``offset`` (1-based for PDFs, None otherwise)."""
        for span in self.page_spans:
            if span.start <= offset < span.end:
                return span.page
        return self.page_spans[-1].page if self.page_spans else None


def _extract_pdf(data: bytes) -> ExtractedDoc:
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:  # pypdf raises a grab-bag of errors
        raise ExtractionError(f"Could not read PDF: {exc}") from exc

    if reader.is_encrypted:
        # Best-effort: try the empty password, common for "protected" exports.
        try:
            reader.decrypt("")
        except Exception as exc:
            raise ExtractionError("PDF is encrypted and cannot be read") from exc

    parts: list[str] = []
    spans: list[PageSpan] = []
    cursor = 0
    for i, page in enumerate(reader.pages, start=1):
        page_text = (page.extract_text() or "").strip()
        if not page_text:
            continue
        block = page_text + "\n\n"
        spans.append(PageSpan(start=cursor, end=cursor + len(block), page=i))
        parts.append(block)
        cursor += len(block)

    full = "".join(parts).strip()
    if not full:
        raise ExtractionError(
            "No extractable text found — the PDF may be scanned images (OCR not supported)"
        )
    return ExtractedDoc(text=full, page_spans=spans)


def _extract_text(data: bytes) -> ExtractedDoc:
    text = data.decode("utf-8", errors="replace").strip()
    if not text:
        raise ExtractionError("File is empty")
    return ExtractedDoc(text=text, page_spans=[PageSpan(0, len(text), None)])


def extract_text(filename: str, content_type: str, data: bytes) -> ExtractedDoc:
    """Dispatch on file type and return extracted text + page map."""
    name = filename.lower()
    if name.endswith(".pdf") or content_type == "application/pdf":
        return _extract_pdf(data)
    if name.endswith((".txt", ".md", ".markdown")) or content_type.startswith("text/"):
        return _extract_text(data)
    # Fallback: try decoding as text; PDFs would have matched above.
    log.warning("extraction.unknown_type", filename=filename, content_type=content_type)
    return _extract_text(data)
