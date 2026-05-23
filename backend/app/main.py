"""FastAPI application entrypoint.

Wires together the routers, CORS, the Redis-backed rate limiter, and a lifespan
that prepares the schema and warms the embedding model so the first request
isn't penalised by a cold start.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app import __version__
from app.api import documents, health, metrics, query
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.rate_limit import limiter
from app.db.init_db import init_db
from app.db.session import dispose_engine
from app.services import embeddings, semantic_cache

log = get_logger(__name__)


async def _init_db_with_retry(attempts: int = 10, delay: float = 2.0) -> None:
    """Tolerate Postgres still booting (common with docker-compose)."""
    for attempt in range(1, attempts + 1):
        try:
            await init_db()
            return
        except Exception as exc:
            if attempt == attempts:
                raise
            log.warning("db.init_retry", attempt=attempt, error=str(exc))
            await asyncio.sleep(delay)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log.info("app.starting", env=settings.app_env, version=__version__)
    await _init_db_with_retry()
    try:
        # CPU-bound model load — keep it off the event loop.
        await asyncio.to_thread(embeddings.warmup)
    except Exception as exc:
        log.warning("embeddings.warmup_failed", error=str(exc))
    yield
    await dispose_engine()
    await semantic_cache.close()
    log.info("app.stopped")


app = FastAPI(
    title="DocVault",
    version=__version__,
    description=(
        "A production-minded RAG platform: grounded answers with citations, "
        "semantic caching, rate limiting, automatic evaluation, and observability."
    ),
    lifespan=lifespan,
)

# Rate limiting (slowapi).
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS for the frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers — probes at root, everything else under /api.
app.include_router(health.router)
app.include_router(documents.router, prefix="/api")
app.include_router(query.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")


@app.get("/", tags=["root"])
async def root() -> dict:
    return {
        "name": "DocVault",
        "version": __version__,
        "docs": "/docs",
        "endpoints": ["/api/documents", "/api/query", "/api/metrics", "/health", "/ready"],
    }
