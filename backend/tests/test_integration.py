"""End-to-end pipeline test: index a document, then answer a question about it.

Everything is real except the Groq call (mocked) — extraction, chunking, local
embeddings, pgvector retrieval, citation mapping and query logging all run. The
semantic cache is bypassed (``use_cache=False``) so the test needs only Postgres
+ pgvector, not Redis.

Runs when ``TEST_DATABASE_URL`` points at a pgvector-enabled Postgres (the CI
service container sets it); skipped otherwise.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="set TEST_DATABASE_URL to a pgvector Postgres to run the integration test",
)


async def test_upload_to_query_pipeline(monkeypatch):
    from app.core.config import settings
    from app.db.base import Base
    from app.db.init_db import init_db
    from app.db.models import Document, DocumentStatus
    from app.db.session import dispose_engine, get_engine, get_sessionmaker
    from app.eval.dataset import load_sample_document
    from app.services.ingestion import index_document
    from app.services.llm import LLMResult
    from app.services.rag import answer_question

    # Point the global engine at the test database and (re)build the schema.
    settings.database_url = os.environ["TEST_DATABASE_URL"]
    await dispose_engine()
    await init_db()

    async def fake_complete(system: str, user: str, **kwargs) -> LLMResult:
        assert "Sources:" in user  # prompt must include retrieved context
        return LLMResult(
            text="Acme Robotics was founded in 2014 [1].",
            prompt_tokens=12,
            completion_tokens=9,
            total_tokens=21,
            model="mock",
        )

    monkeypatch.setattr("app.services.llm.complete", fake_complete)

    sm = get_sessionmaker()
    filename, data = load_sample_document()

    # Upload + background indexing (run inline here).
    async with sm() as session:
        doc = Document(filename=filename, content_type="text/markdown", size_bytes=len(data))
        session.add(doc)
        await session.commit()
        doc_id = doc.id
    await index_document(doc_id, filename, "text/markdown", data)

    try:
        async with sm() as session:
            indexed = await session.get(Document, doc_id)
            assert indexed.status == DocumentStatus.INDEXED
            assert indexed.num_chunks > 0

            result = await answer_question(
                session, "When was Acme Robotics founded?", use_cache=False
            )

        assert "2014" in result.answer
        assert result.num_contexts > 0
        assert any(c["cited"] for c in result.citations)
        assert result.query_log_id is not None
        assert result.context_relevance is not None
    finally:
        async with get_engine().begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await dispose_engine()
