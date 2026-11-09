"""Source documents for the indexing pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine, select

from backend.app.storage.tables.corpus import DatasetVersion, Document


@dataclass(frozen=True)
class SourceDocument:
    id: str
    title: str
    content: str


class PostgresDocumentStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def corpus_hash(self, dataset: str) -> str | None:
        with self.engine.connect() as conn:
            return conn.scalar(
                select(DatasetVersion.corpus_hash).where(DatasetVersion.id == dataset)
            )

    def documents(self) -> list[SourceDocument]:
        query = select(Document.id, Document.title, Document.content).order_by(Document.id)
        with self.engine.connect() as conn:
            return [SourceDocument(*row) for row in conn.execute(query)]
