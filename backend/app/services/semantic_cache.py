"""Semantic response cache (Redis).

A plain key/value cache only helps when two users type *exactly* the same
question. This cache hits when they ask the *same thing in different words*: we
embed the incoming question and compare it (cosine) against cached question
embeddings; above a threshold we return the stored answer and skip the LLM
entirely.

Why it matters: the LLM call is the expensive, slow part. Every hit saves real
money and trims latency from seconds to milliseconds — the dashboard reports
the hit rate so the saving is visible.

Implementation note: we keep a bounded, TTL'd set of entries and score
similarity in-process with NumPy. That's plenty for MVP traffic and needs only
vanilla Redis. The obvious next step — offloading the nearest-neighbour search
to Redis (RediSearch HNSW) or reusing pgvector — is called out in the README.
Redis failures degrade gracefully to a cache miss; they never fail a query.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass

import numpy as np
import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

_ENTRY_PREFIX = "dv:cache:entry:"
_INDEX_KEY = "dv:cache:index"  # ZSET of entry ids scored by creation time

_redis: aioredis.Redis | None = None


def _client() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_dsn, decode_responses=False)
    return _redis


def _entry_key(entry_id: str) -> str:
    return f"{_ENTRY_PREFIX}{entry_id}"


@dataclass
class CacheHit:
    question: str
    payload: dict  # the cached API response body (answer + citations)
    similarity: float


async def lookup(query_embedding: list[float]) -> CacheHit | None:
    """Return the closest cached answer if it clears the similarity threshold."""
    if not settings.semantic_cache_enabled:
        return None
    try:
        r = _client()
        ids = await r.zrevrange(_INDEX_KEY, 0, settings.semantic_cache_max_entries - 1)
        if not ids:
            return None

        pipe = r.pipeline()
        for entry_id in ids:
            pipe.hget(_entry_key(entry_id.decode()), "emb")
        raw_embs = await pipe.execute()

        q = np.asarray(query_embedding, dtype=np.float32)
        best_sim = -1.0
        best_id: bytes | None = None
        stale: list[bytes] = []
        for entry_id, raw in zip(ids, raw_embs, strict=True):
            if raw is None:  # entry expired but index entry lingered
                stale.append(entry_id)
                continue
            emb = np.frombuffer(raw, dtype=np.float32)
            # Vectors are L2-normalised, so dot product == cosine similarity.
            sim = float(np.dot(q, emb))
            if sim > best_sim:
                best_sim, best_id = sim, entry_id

        if stale:
            await r.zrem(_INDEX_KEY, *stale)

        if best_id is None or best_sim < settings.semantic_cache_threshold:
            return None

        data = await r.hgetall(_entry_key(best_id.decode()))
        if not data:
            return None
        return CacheHit(
            question=data[b"question"].decode(),
            payload=json.loads(data[b"payload"]),
            similarity=round(best_sim, 4),
        )
    except Exception as exc:
        log.warning("semantic_cache.lookup_failed", error=str(exc))
        return None


async def store(question: str, query_embedding: list[float], payload: dict) -> None:
    """Persist an answer keyed by its question embedding, with TTL + eviction."""
    if not settings.semantic_cache_enabled:
        return
    try:
        r = _client()
        entry_id = uuid.uuid4().hex
        emb = np.asarray(query_embedding, dtype=np.float32).tobytes()
        key = _entry_key(entry_id)

        pipe = r.pipeline()
        pipe.hset(
            key,
            mapping={
                "question": question.encode(),
                "payload": json.dumps(payload).encode(),
                "emb": emb,
            },
        )
        pipe.expire(key, settings.semantic_cache_ttl_seconds)
        pipe.zadd(_INDEX_KEY, {entry_id: time.time()})
        await pipe.execute()

        # Evict oldest entries beyond the cap.
        size = await r.zcard(_INDEX_KEY)
        overflow = size - settings.semantic_cache_max_entries
        if overflow > 0:
            victims = await r.zrange(_INDEX_KEY, 0, overflow - 1)
            if victims:
                vpipe = r.pipeline()
                for vid in victims:
                    vpipe.delete(_entry_key(vid.decode()))
                vpipe.zrem(_INDEX_KEY, *victims)
                await vpipe.execute()
    except Exception as exc:
        log.warning("semantic_cache.store_failed", error=str(exc))


async def size() -> int:
    try:
        return int(await _client().zcard(_INDEX_KEY))
    except Exception:
        return 0


async def close() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
    _redis = None
