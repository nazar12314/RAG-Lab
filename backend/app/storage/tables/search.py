"""Index profiles, chunks, embeddings and full-text vectors (schema `search`).

A dataset is not an index: every chunk belongs to an index profile, so several chunking or
embedding configurations can coexist over the same corpus snapshot.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.storage.postgres import Base

SCHEMA = "search"

# Matches EMBEDDING_DIMENSION in .env.example; a model with another dimension needs a migration.
EMBEDDING_DIM = 1536


class IndexProfile(Base):
    __tablename__ = "index_profiles"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'building', 'ready', 'failed')", name="status_values"
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    dataset_version_id: Mapped[str] = mapped_column(
        ForeignKey("corpus.dataset_versions.id", ondelete="CASCADE")
    )
    chunker: Mapped[str] = mapped_column(Text)
    chunker_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    embedding_model: Mapped[str | None] = mapped_column(Text)
    embedding_dim: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, default="pending")
    chunk_count: Mapped[int | None] = mapped_column(Integer)
    content_hash: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    built_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentChunk(Base):
    """span_start/span_end are character offsets into corpus.documents.content."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("index_profile_id", "document_id", "ordinal"),
        CheckConstraint("span_start >= 0 AND span_end > span_start", name="span_order"),
        Index("ix_document_chunks_tsv", "tsv", postgresql_using="gin"),
        Index("ix_document_chunks_document", "document_id", "span_start"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    index_profile_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.index_profiles.id", ondelete="CASCADE")
    )
    document_id: Mapped[str] = mapped_column(ForeignKey("corpus.documents.id", ondelete="CASCADE"))
    ordinal: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    span_start: Mapped[int] = mapped_column(Integer)
    span_end: Mapped[int] = mapped_column(Integer)
    section_path: Mapped[str | None] = mapped_column(Text)
    token_count: Mapped[int | None] = mapped_column(Integer)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    # Generated, so keyword search can never drift from the stored chunk text.
    tsv: Mapped[Any] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english', text)", persisted=True)
    )


class ChunkEntity(Base):
    __tablename__ = "chunk_entities"
    __table_args__ = {"schema": SCHEMA}

    chunk_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.document_chunks.id", ondelete="CASCADE"), primary_key=True
    )
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("graph.entities.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    span_start: Mapped[int] = mapped_column(Integer, primary_key=True)
    span_end: Mapped[int] = mapped_column(Integer)
    mention_text: Mapped[str] = mapped_column(Text)
