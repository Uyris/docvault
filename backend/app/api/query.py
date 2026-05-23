"""Question answering endpoint — the expensive, rate-limited path."""

# NOTE: deliberately NOT using `from __future__ import annotations` here. The
# slowapi @limiter.limit decorator wraps the function, and PEP 563 stringized
# annotations would then be resolved against slowapi's module globals — where
# `QueryRequest` is undefined — so FastAPI fails to recognise the Pydantic body
# and treats `payload` as a query param (HTTP 422). Real annotations avoid that.

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.session import get_session
from app.schemas.query import QueryRequest, QueryResponse
from app.services import rag

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
@limiter.limit(settings.rate_limit_query)
async def query(
    request: Request,  # required by slowapi's limiter
    payload: QueryRequest,
    session: AsyncSession = Depends(get_session),
) -> QueryResponse:
    try:
        result = await rag.answer_question(
            session,
            payload.question,
            top_k=payload.top_k,
            document_ids=payload.document_ids,
        )
    except RuntimeError as exc:
        # e.g. GROQ_API_KEY missing / misconfiguration — actionable, not a 500.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    return QueryResponse(
        answer=result.answer,
        citations=result.citations,
        cache_hit=result.cache_hit,
        similarity=result.similarity,
        latency_ms=result.latency_ms,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        total_tokens=result.total_tokens,
        estimated_cost_usd=result.estimated_cost_usd,
        model=result.model,
        num_contexts=result.num_contexts,
        context_relevance=result.context_relevance,
        query_log_id=result.query_log_id,
    )
