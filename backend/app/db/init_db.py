"""Schema bootstrap.

For an MVP we create the schema imperatively at startup instead of pulling in a
migration tool. The order matters: the ``vector`` extension must exist before
the ``chunks.embedding`` column can be created, and the ANN index is built last
with an explicit ops class so we control the distance metric (cosine).

Production note: swap this for Alembic migrations once the schema starts to
evolve — see the "future work" section of the README.
"""

from __future__ import annotations

from sqlalchemy import text

from app.core.config import settings
from app.core.logging import get_logger

# Import models so they register on Base.metadata before create_all.
from app.db import models  # noqa: F401  (side-effect import)
from app.db.base import Base
from app.db.session import get_engine

log = get_logger(__name__)


def _vector_index_sql() -> str:
    """DDL for the approximate-nearest-neighbour index over chunk embeddings.

    We default to **HNSW**: higher build cost but excellent recall/latency and,
    crucially, it needs no training step or row-count tuning the way IVFFlat's
    ``lists`` parameter does. ``vector_cosine_ops`` because we L2-normalise
    embeddings and rank by cosine similarity.
    """
    if settings.vector_index_type.lower() == "ivfflat":
        return (
            "CREATE INDEX IF NOT EXISTS ix_chunks_embedding "
            "ON chunks USING ivfflat (embedding vector_cosine_ops) "
            "WITH (lists = 100)"
        )
    return (
        "CREATE INDEX IF NOT EXISTS ix_chunks_embedding "
        "ON chunks USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


async def init_db() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(_vector_index_sql()))
    log.info(
        "db.initialized",
        vector_index=settings.vector_index_type,
        embedding_dim=settings.embedding_dim,
    )
