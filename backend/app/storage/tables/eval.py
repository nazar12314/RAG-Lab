"""Gold labels and experiment history (schema `eval`).

Readable only by the evaluation service. The `raglab_retriever` role used by retrievers and
agent tools has no privileges on this schema.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.storage.postgres import Base

SCHEMA = "eval"


class Fact(Base):
    """Atomic canonical fact; the stable unit that gold labels and metrics refer to."""

    __tablename__ = "facts"
    __table_args__ = (Index("ix_facts_subject", "subject"), {"schema": SCHEMA})

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    kind: Mapped[str] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(Text)
    predicate: Mapped[str] = mapped_column(Text)
    object: Mapped[str | None] = mapped_column(Text)
    statement: Mapped[str] = mapped_column(Text)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)


class FactSource(Base):
    """A document span or business record stating a fact.

    stance: supports (authoritative), preliminary (early hypothesis, may be wrong),
    contradicts (a source that disagrees with the canonical fact).
    """

    __tablename__ = "fact_sources"
    __table_args__ = (
        CheckConstraint(
            "(source_kind = 'document' AND document_id IS NOT NULL AND span_end > span_start) OR "
            "(source_kind = 'record' AND record_table IS NOT NULL AND record_id IS NOT NULL)",
            name="source_shape",
        ),
        CheckConstraint(
            "stance IN ('supports', 'preliminary', 'contradicts')", name="stance_values"
        ),
        Index("ix_fact_sources_document", "document_id", "span_start"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fact_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.facts.id", ondelete="CASCADE"), index=True
    )
    source_kind: Mapped[str] = mapped_column(Text)
    document_id: Mapped[str | None] = mapped_column(
        ForeignKey("corpus.documents.id", ondelete="CASCADE")
    )
    span_start: Mapped[int | None] = mapped_column(Integer)
    span_end: Mapped[int | None] = mapped_column(Integer)
    record_table: Mapped[str | None] = mapped_column(Text)
    record_id: Mapped[str | None] = mapped_column(Text)
    stance: Mapped[str] = mapped_column(Text)


class EntityMention(Base):
    """Gold entity mentions in documents, for evaluating entity linking and graph extraction."""

    __tablename__ = "entity_mentions"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("corpus.documents.id", ondelete="CASCADE"), index=True
    )
    entity_key: Mapped[str] = mapped_column(Text, index=True)
    span_start: Mapped[int] = mapped_column(Integer)
    span_end: Mapped[int] = mapped_column(Integer)
    surface: Mapped[str] = mapped_column(Text)


class RelationFact(Base):
    __tablename__ = "relation_facts"
    __table_args__ = {"schema": SCHEMA}

    relation_id: Mapped[int] = mapped_column(
        ForeignKey("graph.relations.id", ondelete="CASCADE"), primary_key=True
    )
    fact_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.facts.id", ondelete="CASCADE"), primary_key=True
    )


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint("split IN ('showcase', 'development', 'heldout')", name="split_values"),
        CheckConstraint("answerable OR answer_type = 'abstain'", name="unanswerable_abstains"),
        Index("ix_questions_split_category", "split", "category"),
        {"schema": SCHEMA},
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    split: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    question: Mapped[str] = mapped_column(Text)
    reference_answer: Mapped[str] = mapped_column(Text)
    accepted_answers: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    answer_type: Mapped[str] = mapped_column(Text)
    answerable: Mapped[bool] = mapped_column(Boolean)
    as_of: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)


class QuestionEvidence(Base):
    __tablename__ = "question_evidence"
    __table_args__ = (
        CheckConstraint("requirement IN ('required', 'supporting')", name="requirement_values"),
        {"schema": SCHEMA},
    )

    question_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.questions.id", ondelete="CASCADE"), primary_key=True
    )
    fact_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.facts.id", ondelete="CASCADE"), primary_key=True
    )
    requirement: Mapped[str] = mapped_column(Text)


class QuestionDocument(Base):
    __tablename__ = "question_documents"
    __table_args__ = {"schema": SCHEMA}

    question_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.questions.id", ondelete="CASCADE"), primary_key=True
    )
    document_id: Mapped[str] = mapped_column(
        ForeignKey("corpus.documents.id", ondelete="CASCADE"), primary_key=True
    )


class QuestionPath(Base):
    """Expected graph path steps, by stable entity keys so they apply to any graph version."""

    __tablename__ = "question_paths"
    __table_args__ = {"schema": SCHEMA}

    question_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.questions.id", ondelete="CASCADE"), primary_key=True
    )
    path_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    step_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_key: Mapped[str] = mapped_column(Text)
    relation_type: Mapped[str] = mapped_column(Text)
    target_key: Mapped[str] = mapped_column(Text)


class QuestionTool(Base):
    __tablename__ = "question_tools"
    __table_args__ = {"schema": SCHEMA}

    question_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.questions.id", ondelete="CASCADE"), primary_key=True
    )
    tool_name: Mapped[str] = mapped_column(Text, primary_key=True)
    is_first_tool: Mapped[bool] = mapped_column(Boolean, default=False)


class ExperimentRun(Base):
    """A frozen configuration snapshot.

    Index profile and graph version are kept as plain ids (not foreign keys) so that a
    dataset reseed never deletes experiment history.
    """

    __tablename__ = "experiment_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')", name="status_values"
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, default="queued")
    method: Mapped[str] = mapped_column(Text)
    split: Mapped[str | None] = mapped_column(Text)
    dataset_version_id: Mapped[str] = mapped_column(Text)
    corpus_hash: Mapped[str] = mapped_column(Text)
    index_profile_id: Mapped[str | None] = mapped_column(Text)
    graph_version_id: Mapped[str | None] = mapped_column(Text)
    # Models, prompt versions, top_k, hops, budgets, tool limits, cache state, seeds.
    config: Mapped[dict[str, Any]] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(Text)


class ExperimentResult(Base):
    __tablename__ = "experiment_results"
    __table_args__ = (
        UniqueConstraint("run_id", "question_id", "repetition"),
        CheckConstraint(
            "status IN ('ok', 'abstained', 'unsupported', 'timeout', 'error')",
            name="status_values",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.experiment_runs.id", ondelete="CASCADE"), index=True
    )
    # Not a foreign key: results must survive a reseed of the question tables.
    question_id: Mapped[str] = mapped_column(Text, index=True)
    repetition: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    retrieved_fact_ids: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    graph_paths: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    tool_calls: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    retrieval_latency_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
