"""Local embedding model (sentence-transformers).

Embeddings run on-device (CPU), so there's no per-token API cost and no data
leaves the box for indexing — a deliberate cost/privacy trade-off documented in
the README. The model is heavy to load, so we instantiate it once (lazily) and
reuse it. ``encode`` is CPU-bound and blocking, so async callers hop to a
worker thread to avoid stalling the event loop.

Vectors are L2-normalised, which lets cosine similarity reduce to a dot product
and matches the ``vector_cosine_ops`` index in Postgres.
"""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING

from app.core.config import settings
from app.core.logging import get_logger

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

log = get_logger(__name__)

_model: SentenceTransformer | None = None
_lock = threading.Lock()


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer

                log.info("embeddings.loading", model=settings.embedding_model)
                _model = SentenceTransformer(settings.embedding_model)
                dim = _model.get_sentence_embedding_dimension()
                if dim != settings.embedding_dim:
                    raise RuntimeError(
                        f"EMBEDDING_DIM={settings.embedding_dim} but model "
                        f"'{settings.embedding_model}' produces {dim}-d vectors. "
                        "Fix EMBEDDING_DIM (and re-index) to match the model."
                    )
                log.info("embeddings.loaded", model=settings.embedding_model, dim=dim)
    return _model


def _encode(texts: list[str]) -> list[list[float]]:
    model = _get_model()
    vectors = model.encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return vectors.tolist()


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts (used during indexing)."""
    if not texts:
        return []
    return await asyncio.to_thread(_encode, texts)


async def embed_query(text: str) -> list[float]:
    """Embed a single query string."""
    [vector] = await asyncio.to_thread(_encode, [text])
    return vector


def warmup() -> None:
    """Pre-load the model at startup so the first request isn't slow."""
    _get_model()
