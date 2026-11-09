"""PostgreSQL access for index profiles, chunks and vector similarity search."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Connection, Engine, Row, delete, insert, select, text

from backend.app.models.contracts import IndexProfile as IndexProfileModel
from backend.app.storage.tables import RETRIEVER_ROLE
from backend.app.storage.tables.corpus import Document
from backend.app.storage.tables.search import DocumentChunk, IndexProfile

_CHUNK_COLUMNS = (
    DocumentChunk.document_id,
    DocumentChunk.ordinal,
    DocumentChunk.text,
    DocumentChunk.span_start,
    DocumentChunk.span_end,
    DocumentChunk.section_path,
    Document.title,
    Document.doc_type,
    Document.source_uri,
    Document.created_at,
)


@dataclass(frozen=True)
class StoredChunk:
    document_id: str
    ordinal: int
    text: str
    span_start: int
    span_end: int
    section_path: str | None
    title: str
    doc_type: str
    source_uri: str
    created_at: datetime


@dataclass(frozen=True)
class NewChunk:
    document_id: str
    ordinal: int
    text: str
    span_start: int
    span_end: int
    section_path: str | None
    token_count: int
    embedding: list[float]


def _stored(row: Row[Any]) -> StoredChunk:
    return StoredChunk(*row[: len(_CHUNK_COLUMNS)])


class PostgresSearchStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @contextmanager
    def _retriever_connection(self) -> Iterator[Connection]:
        """Reads run as the role that cannot see `eval`, so gold labels cannot leak in."""
        with self.engine.begin() as conn:
            conn.execute(text(f"SET LOCAL ROLE {RETRIEVER_ROLE}"))
            yield conn

    def _profiles(self, *conditions: Any) -> list[IndexProfileModel]:
        query = select(IndexProfile).where(*conditions).order_by(IndexProfile.id)
        with self._retriever_connection() as conn:
            return [IndexProfileModel(**row._mapping) for row in conn.execute(query)]

    def ready_profiles(self, dataset: str) -> list[IndexProfileModel]:
        return self._profiles(
            IndexProfile.dataset_version_id == dataset, IndexProfile.status == "ready"
        )

    def profile(self, profile_id: str) -> IndexProfileModel | None:
        found = self._profiles(IndexProfile.id == profile_id)
        return found[0] if found else None

    def chunks(self, profile_id: str) -> list[StoredChunk]:
        query = (
            select(*_CHUNK_COLUMNS)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(DocumentChunk.index_profile_id == profile_id)
            .order_by(DocumentChunk.document_id, DocumentChunk.ordinal)
        )
        with self._retriever_connection() as conn:
            return [_stored(row) for row in conn.execute(query)]

    def nearest(
        self, profile_id: str, vector: list[float], top_k: int
    ) -> list[tuple[StoredChunk, float]]:
        """Exact cosine search; the corpus is small enough not to need an approximate index."""
        distance = DocumentChunk.embedding.cosine_distance(vector)
        query = (
            select(*_CHUNK_COLUMNS, distance.label("distance"))
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                DocumentChunk.index_profile_id == profile_id,
                DocumentChunk.embedding.is_not(None),
            )
            .order_by(distance, DocumentChunk.document_id, DocumentChunk.ordinal)
            .limit(top_k)
        )
        with self._retriever_connection() as conn:
            return [(_stored(row), 1.0 - row.distance) for row in conn.execute(query)]

    def replace_index(self, profile: dict[str, Any], chunks: Sequence[NewChunk]) -> None:
        """Swaps a whole index in one transaction, so readers never see a partial build."""
        with self.engine.begin() as conn:
            conn.execute(delete(IndexProfile).where(IndexProfile.id == profile["id"]))
            conn.execute(
                insert(IndexProfile).values(
                    **profile,
                    status="ready",
                    chunk_count=len(chunks),
                    built_at=datetime.now(UTC),
                )
            )
            conn.execute(
                insert(DocumentChunk),
                [{"index_profile_id": profile["id"], **vars(chunk)} for chunk in chunks],
            )

    def delete_profile(self, profile_id: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(delete(IndexProfile).where(IndexProfile.id == profile_id))
