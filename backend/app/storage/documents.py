"""Source documents for the indexing pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Engine, select

from backend.app.storage.search import retriever_connection
from backend.app.storage.tables.corpus import DatasetVersion, Document


@dataclass(frozen=True)
class SourceDocument:
    id: str
    title: str
    content: str


@dataclass(frozen=True)
class FullDocument:
    id: str
    title: str
    doc_type: str
    source_uri: str
    created_at: datetime
    content: str


class PostgresDocumentStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def corpus_hash(self, dataset: str) -> str | None:
        with self.engine.connect() as conn:
            return conn.scalar(
                select(DatasetVersion.corpus_hash).where(DatasetVersion.id == dataset)
            )

    def document(self, document_id: str) -> FullDocument | None:
        query = select(
            Document.id,
            Document.title,
            Document.doc_type,
            Document.source_uri,
            Document.created_at,
            Document.content,
        ).where(Document.id == document_id)
        with retriever_connection(self.engine) as conn:
            row = conn.execute(query).first()
        return FullDocument(*row) if row else None

    def documents(self) -> list[SourceDocument]:
        query = select(Document.id, Document.title, Document.content).order_by(Document.id)
        with self.engine.connect() as conn:
            return [SourceDocument(*row) for row in conn.execute(query)]
