"""Liveness / readiness checks."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app import __version__
from app.db.session import get_engine
from app.services import semantic_cache

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Lightweight liveness probe — no external dependencies touched."""
    return {"status": "ok", "version": __version__}


@router.get("/ready")
async def ready() -> dict:
    """Readiness probe — verifies Postgres and Redis are reachable."""
    checks: dict[str, str] = {}

    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:
        checks["postgres"] = f"error: {exc}"

    try:
        await semantic_cache._client().ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"

    ready = all(v == "ok" for v in checks.values())
    return {"ready": ready, "checks": checks}
