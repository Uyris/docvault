"""pgvector retrieval.

Postgres *is* the vector store here. Using the database every team already runs
— rather than bolting on a dedicated vector DB — keeps the operational surface
small and lets chunk text, metadata and embeddings live in one transactional
place. The ANN index (HNSW, cosine) is created in ``init_db``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.models import Chunk
from app.services.chunking import TextChunk


@dataclass
class Retrieved:
    chunk: Chunk
    score: float  # cosine similarity in [0, 1]; higher is closer


async def add_chunks(
    session: AsyncSession,
    document_id: uuid.UUID,
    chunks: list[TextChunk],
    embeddings: list[list[float]],
) -> int:
    """Persist chunks + their embeddings for one document."""
    rows = [
        Chunk(
            document_id=document_id,
            chunk_index=c.index,
            content=c.content,
            char_start=c.char_start,
            char_end=c.char_end,
            page=c.page,
            embedding=emb,
        )
        for c, emb in zip(chunks, embeddings, strict=True)
    ]
    session.add_all(rows)
    await session.flush()
    return len(rows)


async def search(
    session: AsyncSession,
    query_embedding: list[float],
    top_k: int,
    document_ids: list[uuid.UUID] | None = None,
) -> list[Retrieved]:
    """Return the ``top_k`` most similar chunks, optionally scoped to documents."""
    distance = Chunk.embedding.cosine_distance(query_embedding).label("distance")
    stmt = (
        select(Chunk, distance)
        .options(joinedload(Chunk.document))  # eager-load: async forbids lazy access
        .order_by(distance)
        .limit(top_k)
    )
    if document_ids:
        stmt = stmt.where(Chunk.document_id.in_(document_ids))

    result = await session.execute(stmt)
    return [Retrieved(chunk=chunk, score=1.0 - float(dist)) for chunk, dist in result.all()]
