"""Document indexing pipeline (runs in the background).

The upload endpoint returns immediately with a ``pending`` document; this
function does the slow work — extract → chunk → embed → store — and flips the
status to ``indexed`` (or ``failed`` with a reason). It owns its own DB session
because the request that scheduled it has already returned.

For an MVP, FastAPI ``BackgroundTasks`` is the right amount of async: no broker
to run. The clean seam (one function, one document id) means swapping in Celery
or arq later is a localized change — noted as future work in the README.
"""

from __future__ import annotations

import uuid

from app.core.logging import get_logger
from app.db.models import Document, DocumentStatus
from app.db.session import get_sessionmaker
from app.services import embeddings, vector_store
from app.services.chunking import chunk_document
from app.services.extraction import ExtractionError, extract_text

log = get_logger(__name__)


async def index_document(
    document_id: uuid.UUID, filename: str, content_type: str, data: bytes
) -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        doc = await session.get(Document, document_id)
        if doc is None:
            log.error("ingestion.document_missing", document_id=str(document_id))
            return
        doc.status = DocumentStatus.PROCESSING
        await session.commit()

        try:
            extracted = extract_text(filename, content_type, data)
            chunks = chunk_document(extracted)
            if not chunks:
                raise ExtractionError("Document produced no chunks")

            vectors = await embeddings.embed_texts([c.content for c in chunks])
            count = await vector_store.add_chunks(session, document_id, chunks, vectors)

            doc.num_chunks = count
            doc.num_chars = len(extracted.text)
            doc.status = DocumentStatus.INDEXED
            doc.error = None
            await session.commit()
            log.info(
                "ingestion.indexed",
                document_id=str(document_id),
                filename=filename,
                chunks=count,
                chars=doc.num_chars,
            )
        except Exception as exc:
            await session.rollback()
            doc = await session.get(Document, document_id)
            if doc is not None:
                doc.status = DocumentStatus.FAILED
                doc.error = str(exc)[:1000]
                await session.commit()
            log.error(
                "ingestion.failed",
                document_id=str(document_id),
                filename=filename,
                error=str(exc),
            )
