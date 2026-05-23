"""RAG orchestration — the hot path for answering a question.

    embed → semantic-cache lookup → (miss) retrieve top-k → prompt → LLM →
    citations → cache → log

Every answer is grounded in retrieved chunks and carries citations back to the
source. Every call is logged with latency, tokens, estimated cost and a
relevance signal, which is what the /metrics dashboard later aggregates.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from time import perf_counter

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import QueryLog
from app.services import embeddings, llm, semantic_cache, vector_store
from app.services.citations import build_citations, citation_to_dict
from app.services.prompts import RAG_SYSTEM_PROMPT, build_user_prompt

log = get_logger(__name__)

_NO_CONTEXT_MSG = (
    "I could not find this in the provided documents. "
    "Try uploading a relevant document first."
)


@dataclass
class RAGResult:
    answer: str
    citations: list[dict]
    cache_hit: bool = False
    similarity: float | None = None
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    model: str = ""
    num_contexts: int = 0
    context_relevance: float | None = None
    query_log_id: uuid.UUID | None = None
    retrieved_chunk_ids: list[str] = field(default_factory=list)


async def _record(session: AsyncSession, result: RAGResult, question: str) -> None:
    row = QueryLog(
        question=question,
        answer=result.answer,
        latency_ms=result.latency_ms,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        total_tokens=result.total_tokens,
        estimated_cost_usd=result.estimated_cost_usd,
        cache_hit=result.cache_hit,
        model=result.model,
        top_k=settings.retrieval_top_k,
        num_contexts=result.num_contexts,
        retrieved_chunk_ids=result.retrieved_chunk_ids,
        context_relevance=result.context_relevance,
    )
    session.add(row)
    await session.commit()
    result.query_log_id = row.id


async def answer_question(
    session: AsyncSession,
    question: str,
    *,
    top_k: int | None = None,
    document_ids: list[uuid.UUID] | None = None,
    use_cache: bool = True,
) -> RAGResult:
    t0 = perf_counter()
    top_k = top_k or settings.retrieval_top_k
    query_embedding = await embeddings.embed_query(question)

    # 1. Semantic cache — return a paraphrase match without touching the LLM.
    #    Disabled during evaluation so we measure the real retrieve→generate path.
    hit = await semantic_cache.lookup(query_embedding) if use_cache else None
    if hit is not None:
        result = RAGResult(
            answer=hit.payload["answer"],
            citations=hit.payload.get("citations", []),
            cache_hit=True,
            similarity=hit.similarity,
            latency_ms=round((perf_counter() - t0) * 1000, 2),
            model="cache",
            num_contexts=len(hit.payload.get("citations", [])),
        )
        await _record(session, result, question)
        log.info("query.answered", cache_hit=True, similarity=hit.similarity,
                 latency_ms=result.latency_ms)
        return result

    # 2. Retrieve.
    contexts = await vector_store.search(session, query_embedding, top_k, document_ids)
    if not contexts:
        result = RAGResult(
            answer=_NO_CONTEXT_MSG,
            citations=[],
            latency_ms=round((perf_counter() - t0) * 1000, 2),
            model=settings.llm_model,
        )
        await _record(session, result, question)
        return result

    # 3. Prompt + generate.
    user_prompt = build_user_prompt(question, contexts)
    completion = await llm.complete(RAG_SYSTEM_PROMPT, user_prompt)

    # 4. Citations + cheap relevance signal (mean retrieval similarity).
    citations = [citation_to_dict(c) for c in build_citations(completion.text, contexts)]
    context_relevance = round(sum(c.score for c in contexts) / len(contexts), 4)

    result = RAGResult(
        answer=completion.text,
        citations=citations,
        cache_hit=False,
        latency_ms=round((perf_counter() - t0) * 1000, 2),
        prompt_tokens=completion.prompt_tokens,
        completion_tokens=completion.completion_tokens,
        total_tokens=completion.total_tokens,
        estimated_cost_usd=llm.estimate_cost(
            completion.prompt_tokens, completion.completion_tokens
        ),
        model=completion.model,
        num_contexts=len(contexts),
        context_relevance=context_relevance,
        retrieved_chunk_ids=[str(c.chunk.id) for c in contexts],
    )

    # 5. Cache + log.
    if use_cache:
        await semantic_cache.store(
            question, query_embedding, {"answer": result.answer, "citations": result.citations}
        )
    await _record(session, result, question)
    log.info(
        "query.answered",
        cache_hit=False,
        latency_ms=result.latency_ms,
        total_tokens=result.total_tokens,
        cost_usd=result.estimated_cost_usd,
        contexts=result.num_contexts,
        context_relevance=context_relevance,
    )
    return result
