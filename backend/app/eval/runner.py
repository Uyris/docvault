"""Run the evaluation suite end-to-end and produce a report.

Indexes the gold document, runs every question through the *real* RAG pipeline
(cache disabled so we measure retrieval + generation, not a cached echo), scores
each answer, and writes the eval scores back onto the corresponding QueryLog row
so they also show up on the /metrics dashboard.
"""

from __future__ import annotations

from datetime import UTC, datetime
from statistics import mean

from sqlalchemy import delete

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Document, QueryLog
from app.db.session import get_sessionmaker
from app.eval import metrics
from app.eval.dataset import load_dataset, load_sample_document
from app.services import rag
from app.services.ingestion import index_document

log = get_logger(__name__)


async def _reindex_sample() -> None:
    """Replace any prior copy of the gold document with a freshly indexed one."""
    filename, data = load_sample_document()
    sm = get_sessionmaker()
    async with sm() as session:
        await session.execute(delete(Document).where(Document.filename == filename))
        doc = Document(filename=filename, content_type="text/markdown", size_bytes=len(data))
        session.add(doc)
        await session.commit()
        doc_id = doc.id
    await index_document(doc_id, filename, "text/markdown", data)


async def run_evaluation(*, reindex: bool = True) -> dict:
    dataset = load_dataset()
    if reindex:
        log.info("eval.reindexing", document=dataset.document_filename)
        await _reindex_sample()

    sm = get_sessionmaker()
    items_report: list[dict] = []

    async with sm() as session:
        for item in dataset.items:
            res = await rag.answer_question(session, item.question, use_cache=False)
            contexts = [c["content"] for c in res.citations]

            faith = await metrics.faithfulness(res.answer, contexts) if contexts else None
            relevance = await metrics.answer_relevance(item.question, res.answer)
            ctx_rel = res.context_relevance or 0.0
            correctness = (
                await metrics.answer_correctness(res.answer, item.reference_answer)
                if item.answerable
                else None
            )

            # Persist judge scores back onto the query log → visible on the dashboard.
            if res.query_log_id is not None:
                row = await session.get(QueryLog, res.query_log_id)
                if row is not None:
                    row.faithfulness = faith.score if faith else None
                    row.answer_relevance = relevance.score
                    await session.commit()

            items_report.append(
                {
                    "id": item.id,
                    "question": item.question,
                    "answer": res.answer,
                    "answerable": item.answerable,
                    "faithfulness": faith.score if faith else None,
                    "answer_relevance": relevance.score,
                    "context_relevance": ctx_rel,
                    "answer_correctness": correctness,
                    "num_contexts": res.num_contexts,
                }
            )
            log.info(
                "eval.item",
                id=item.id,
                faithfulness=faith.score if faith else None,
                answer_relevance=relevance.score,
                context_relevance=ctx_rel,
            )

    def _mean(key: str, only_answerable: bool = False) -> float | None:
        vals = [
            r[key]
            for r in items_report
            if r[key] is not None and (not only_answerable or r["answerable"])
        ]
        return round(mean(vals), 4) if vals else None

    aggregates = {
        "faithfulness": _mean("faithfulness"),
        "answer_relevance": _mean("answer_relevance"),
        "context_relevance": _mean("context_relevance"),
        "answer_correctness": _mean("answer_correctness", only_answerable=True),
    }

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "model": settings.llm_model,
        "eval_model": settings.llm_eval_model,
        "embedding_model": settings.embedding_model,
        "dataset_size": len(dataset.items),
        "aggregates": aggregates,
        "items": items_report,
    }
