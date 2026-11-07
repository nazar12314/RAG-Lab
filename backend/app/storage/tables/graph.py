"""Knowledge graph tables (schema `graph`).

Every node and edge belongs to a graph version, so the curated upper-bound graph and one or
more extracted graphs can be compared side by side over the same corpus.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.storage.postgres import Base

SCHEMA = "graph"


class GraphVersion(Base):
    __tablename__ = "graph_versions"
    __table_args__ = (
        CheckConstraint("kind IN ('curated', 'extracted')", name="kind_values"),
        {"schema": SCHEMA},
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    dataset_version_id: Mapped[str] = mapped_column(
        ForeignKey("corpus.dataset_versions.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(Text)
    # Extracted graphs record how they were produced; chunk-based extraction depends on the index.
    extractor_model: Mapped[str | None] = mapped_column(Text)
    extractor_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    index_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("search.index_profiles.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    notes: Mapped[str | None] = mapped_column(Text)


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = (
        UniqueConstraint("graph_version_id", "key"),
        Index("ix_entities_type", "graph_version_id", "entity_type"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    graph_version_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.graph_versions.id", ondelete="CASCADE")
    )
    key: Mapped[str] = mapped_column(Text)
    entity_type: Mapped[str] = mapped_column(Text)
    canonical_name: Mapped[str] = mapped_column(Text)
    # "<table>/<id>" pointer to the corpus record this entity represents, when there is one.
    external_ref: Mapped[str | None] = mapped_column(Text)


class EntityAlias(Base):
    __tablename__ = "entity_aliases"
    __table_args__ = (
        Index("ix_entity_aliases_norm", "alias_norm"),
        {"schema": SCHEMA},
    )

    entity_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.entities.id", ondelete="CASCADE"), primary_key=True
    )
    alias: Mapped[str] = mapped_column(Text, primary_key=True)
    alias_norm: Mapped[str] = mapped_column(Text, Computed("lower(alias)", persisted=True))


class Relation(Base):
    """Directed, typed edge: source --relation_type--> target."""

    __tablename__ = "relations"
    __table_args__ = (
        UniqueConstraint("graph_version_id", "key"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence_range"),
        CheckConstraint(
            "verified_status IN ('verified', 'unverified', 'refuted')",
            name="verified_status_values",
        ),
        Index("ix_relations_source", "source_entity_id", "relation_type"),
        Index("ix_relations_target", "target_entity_id", "relation_type"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    graph_version_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.graph_versions.id", ondelete="CASCADE")
    )
    key: Mapped[str] = mapped_column(Text)
    source_entity_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.entities.id", ondelete="CASCADE")
    )
    target_entity_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.entities.id", ondelete="CASCADE")
    )
    relation_type: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    verified_status: Mapped[str] = mapped_column(Text)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)


class RelationEvidence(Base):
    """Where an edge comes from: a document span (optionally a chunk) or a corpus record."""

    __tablename__ = "relation_evidence"
    __table_args__ = (
        CheckConstraint(
            "(evidence_kind = 'document' AND document_id IS NOT NULL AND span_start IS NOT NULL "
            "AND span_end > span_start) OR "
            "(evidence_kind = 'record' AND record_table IS NOT NULL AND record_id IS NOT NULL)",
            name="evidence_shape",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    relation_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.relations.id", ondelete="CASCADE"), index=True
    )
    evidence_kind: Mapped[str] = mapped_column(Text)
    document_id: Mapped[str | None] = mapped_column(
        ForeignKey("corpus.documents.id", ondelete="CASCADE"), index=True
    )
    span_start: Mapped[int | None] = mapped_column(Integer)
    span_end: Mapped[int | None] = mapped_column(Integer)
    chunk_id: Mapped[int | None] = mapped_column(
        ForeignKey("search.document_chunks.id", ondelete="CASCADE")
    )
    record_table: Mapped[str | None] = mapped_column(Text)
    record_id: Mapped[str | None] = mapped_column(Text)
