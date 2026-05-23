"""Observability / metrics API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class LatencyStats(BaseModel):
    avg_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float


class ScoreStats(BaseModel):
    faithfulness_avg: float | None = None
    answer_relevance_avg: float | None = None
    context_relevance_avg: float | None = None


class VolumePoint(BaseModel):
    day: str
    count: int


class MetricsResponse(BaseModel):
    total_queries: int
    cache_hits: int
    cache_hit_rate: float
    total_cost_usd: float
    avg_cost_per_query_usd: float
    total_tokens: int
    latency: LatencyStats
    scores: ScoreStats
    volume_by_day: list[VolumePoint]
    documents_indexed: int
    chunks_indexed: int
    cache_size: int
    generated_at: datetime
