"""ORM models.

Three tables tell the whole story:

* ``Document``  — one uploaded file and its indexing status.
* ``Chunk``     — a slice of a document plus its embedding vector. Carries the
  character offsets/page so the API can return *citations*, not just text.
* ``QueryLog``  — one row per answered question, capturing latency, tokens,
  cost, cache hit/miss and eval scores. This is the raw material the /metrics
  dashboard aggregates.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.db.base import Base, TimestampMixin


class DocumentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DocumentStatus.PENDING, index=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    num_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    num_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    chunks: Mapped[list[Chunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Chunk(Base, TimestampMixin):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dim))

    document: Mapped[Document] = relationship(back_populates="chunks")


class QueryLog(Base):
    __tablename__ = "query_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False, default="")

    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    cache_hit: Mapped[bool] = mapped_column(nullable=False, default=False, index=True)
    model: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    top_k: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    num_contexts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retrieved_chunk_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # Eval scores — populated on demand (inline eval or the eval runner).
    faithfulness: Mapped[float | None] = mapped_column(Float, nullable=True)
    answer_relevance: Mapped[float | None] = mapped_column(Float, nullable=True)
    context_relevance: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


# Composite index used when reconstructing a document in chunk order.
Index("ix_chunks_document_order", Chunk.document_id, Chunk.chunk_index)
