"""Rate limiting (slowapi + Redis).

The LLM endpoints are the expensive ones, so they get a tighter budget than the
rest of the API. Counters live in Redis so the limit holds across multiple
worker processes — an in-memory limiter would let each worker grant the full
quota. Limits and the on/off switch come from settings.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.rate_limit_default],
    storage_uri=settings.redis_dsn,
    enabled=settings.rate_limit_enabled,
    headers_enabled=True,  # emit X-RateLimit-* headers
)
