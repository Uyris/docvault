"""Aggregations behind the /metrics dashboard.

Turns the raw ``query_logs`` rows into the numbers a reviewer actually wants to
see in 60 seconds: how fast (p50/p95/p99), how cheap (cost + cache-hit rate),
and how good (eval-score averages). Counts and sums run in SQL; latency
percentiles are computed in Python over a bounded recent window so the query
stays portable across Postgres and the SQLite used in tests.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Document, DocumentStatus, QueryLog
from app.services import semantic_cache

_LATENCY_WINDOW = 10_000  # percentiles over the most recent N queries


def _round(value: float | None, ndigits: int = 4) -> float | None:
    return round(float(value), ndigits) if value is not None else None


async def compute_metrics(session: AsyncSession) -> dict:
    agg = (
        await session.execute(
            select(
                func.count(QueryLog.id),
                func.coalesce(func.sum(cast(QueryLog.cache_hit, Integer)), 0),
                func.coalesce(func.sum(QueryLog.estimated_cost_usd), 0.0),
                func.coalesce(func.sum(QueryLog.total_tokens), 0),
                func.avg(QueryLog.faithfulness),
                func.avg(QueryLog.answer_relevance),
                func.avg(QueryLog.context_relevance),
            )
        )
    ).one()
    total, cache_hits, total_cost, total_tokens, faith, ans_rel, ctx_rel = agg

    # Latency percentiles over a recent window.
    lat_rows = await session.execute(
        select(QueryLog.latency_ms).order_by(QueryLog.created_at.desc()).limit(_LATENCY_WINDOW)
    )
    latencies = [float(r[0]) for r in lat_rows]
    if latencies:
        arr = np.asarray(latencies)
        latency = {
            "avg_ms": round(float(arr.mean()), 2),
            "p50_ms": round(float(np.percentile(arr, 50)), 2),
            "p95_ms": round(float(np.percentile(arr, 95)), 2),
            "p99_ms": round(float(np.percentile(arr, 99)), 2),
            "max_ms": round(float(arr.max()), 2),
        }
    else:
        latency = {"avg_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0, "max_ms": 0.0}

    # Volume by calendar day.
    day = func.date(QueryLog.created_at)
    vol_rows = await session.execute(
        select(day.label("day"), func.count()).group_by(day).order_by(day)
    )
    volume_by_day = [{"day": str(d), "count": int(c)} for d, c in vol_rows]

    docs_indexed = (
        await session.execute(
            select(func.count(Document.id)).where(Document.status == DocumentStatus.INDEXED)
        )
    ).scalar_one()
    chunks_indexed = (await session.execute(select(func.count(Chunk.id)))).scalar_one()

    total = int(total)
    cache_hits = int(cache_hits)
    total_cost = float(total_cost)

    return {
        "total_queries": total,
        "cache_hits": cache_hits,
        "cache_hit_rate": round(cache_hits / total, 4) if total else 0.0,
        "total_cost_usd": round(total_cost, 6),
        "avg_cost_per_query_usd": round(total_cost / total, 8) if total else 0.0,
        "total_tokens": int(total_tokens),
        "latency": latency,
        "scores": {
            "faithfulness_avg": _round(faith),
            "answer_relevance_avg": _round(ans_rel),
            "context_relevance_avg": _round(ctx_rel),
        },
        "volume_by_day": volume_by_day,
        "documents_indexed": int(docs_indexed),
        "chunks_indexed": int(chunks_indexed),
        "cache_size": await semantic_cache.size(),
        "generated_at": datetime.now(UTC),
    }
