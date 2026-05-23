"""Query API schemas."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    document_ids: list[uuid.UUID] | None = Field(
        default=None, description="Optional: restrict retrieval to these documents."
    )


class CitationOut(BaseModel):
    marker: int
    cited: bool
    document_id: str
    filename: str
    chunk_id: str
    page: int | None = None
    char_start: int
    char_end: int
    score: float
    content: str


class QueryResponse(BaseModel):
    answer: str
    citations: list[CitationOut]
    cache_hit: bool
    similarity: float | None = None
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    model: str
    num_contexts: int
    context_relevance: float | None = None
    query_log_id: uuid.UUID | None = None
