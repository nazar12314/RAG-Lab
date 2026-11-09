"""PostgreSQL access for knowledge graph lookup and bounded traversal."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from sqlalchemy import Engine, and_, select, text
from sqlalchemy.orm import aliased

from backend.app.storage.search import (
    CHUNK_COLUMNS,
    StoredChunk,
    retriever_connection,
    stored_chunk,
)
from backend.app.storage.tables.corpus import Document
from backend.app.storage.tables.graph import (
    Entity,
    EntityAlias,
    GraphVersion,
    Relation,
    RelationEvidence,
)
from backend.app.storage.tables.search import DocumentChunk

MAX_WALKS = 5000
# Sharing a team or subsystem says nothing causal, so walks may end at these but not pass through.
ENDPOINT_ONLY_TYPES = ("team", "subsystem")

_WALK = text(
    """
    WITH RECURSIVE undirected AS (
        SELECT id, source_entity_id AS here, target_entity_id AS there
        FROM graph.relations WHERE graph_version_id = :version
        UNION ALL
        SELECT id, target_entity_id, source_entity_id
        FROM graph.relations WHERE graph_version_id = :version
    ), walk AS (
        SELECT u.there AS node, ARRAY[u.id] AS relations, ARRAY[u.here, u.there] AS nodes, 1 AS hops
        FROM undirected u
        JOIN graph.entities seed ON seed.id = u.here
        WHERE seed.graph_version_id = :version AND seed.key = ANY(:seeds)
        UNION ALL
        SELECT u.there, w.relations || u.id, w.nodes || u.there, w.hops + 1
        FROM walk w
        JOIN graph.entities current ON current.id = w.node
        JOIN undirected u ON u.here = w.node
        WHERE w.hops < :hops
          AND NOT u.there = ANY(w.nodes)
          AND NOT current.entity_type = ANY(:endpoint_only)
    )
    SELECT relations FROM walk ORDER BY hops, relations LIMIT :limit
    """
)


@dataclass(frozen=True)
class GraphEntity:
    key: str
    name: str
    entity_type: str


@dataclass(frozen=True)
class GraphEdge:
    id: int
    source: str
    target: str
    relation_type: str
    confidence: float
    verified_status: str
    valid_from: date | None
    valid_to: date | None

    @property
    def statement(self) -> str:
        validity = ""
        if self.valid_from or self.valid_to:
            validity = f" (from {self.valid_from or 'start'} until {self.valid_to or 'now'})"
        refuted = " [refuted]" if self.verified_status == "refuted" else ""
        return f"{self.source} -{self.relation_type}-> {self.target}{validity}{refuted}"


class PostgresGraphStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def curated_version(self, dataset: str) -> str | None:
        query = select(GraphVersion.id).where(
            GraphVersion.dataset_version_id == dataset, GraphVersion.kind == "curated"
        )
        with retriever_connection(self.engine) as conn:
            return conn.scalar(query)

    def alias_matches(self, version: str, text_norm: str) -> list[tuple[str, GraphEntity]]:
        """Every alias that occurs in the normalized text, with the entity it names."""
        columns = (Entity.key, Entity.canonical_name, Entity.entity_type)
        alias_query = (
            select(EntityAlias.alias_norm, *columns)
            .join(Entity, Entity.id == EntityAlias.entity_id)
            .where(
                Entity.graph_version_id == version,
                text("position(graph.entity_aliases.alias_norm in :norm) > 0"),
            )
        )
        with retriever_connection(self.engine) as conn:
            rows = conn.execute(alias_query, {"norm": text_norm})
            return [(row[0], GraphEntity(*row[1:])) for row in rows]

    def walks(self, version: str, seeds: Sequence[str], hops: int) -> list[tuple[int, ...]]:
        params = {
            "version": version,
            "seeds": list(seeds),
            "hops": hops,
            "endpoint_only": list(ENDPOINT_ONLY_TYPES),
            "limit": MAX_WALKS,
        }
        with retriever_connection(self.engine) as conn:
            return [tuple(row[0]) for row in conn.execute(_WALK, params)]

    def edges(self, relation_ids: Sequence[int]) -> dict[int, GraphEdge]:
        source, target = aliased(Entity), aliased(Entity)
        query = (
            select(
                Relation.id,
                source.canonical_name,
                target.canonical_name,
                Relation.relation_type,
                Relation.confidence,
                Relation.verified_status,
                Relation.valid_from,
                Relation.valid_to,
            )
            .join(source, source.id == Relation.source_entity_id)
            .join(target, target.id == Relation.target_entity_id)
            .where(Relation.id.in_(relation_ids))
        )
        with retriever_connection(self.engine) as conn:
            return {row[0]: GraphEdge(*row) for row in conn.execute(query)}

    def evidence_chunks(
        self, profile_id: str, relation_ids: Sequence[int]
    ) -> list[tuple[int, StoredChunk]]:
        """Chunks of this index overlapping a document span that backs one of the relations."""
        query = (
            select(RelationEvidence.relation_id, *CHUNK_COLUMNS)
            .join(
                DocumentChunk,
                and_(
                    DocumentChunk.document_id == RelationEvidence.document_id,
                    DocumentChunk.span_start < RelationEvidence.span_end,
                    DocumentChunk.span_end > RelationEvidence.span_start,
                ),
            )
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                RelationEvidence.relation_id.in_(relation_ids),
                RelationEvidence.evidence_kind == "document",
                DocumentChunk.index_profile_id == profile_id,
            )
            .order_by(
                RelationEvidence.relation_id, DocumentChunk.document_id, DocumentChunk.ordinal
            )
        )
        with retriever_connection(self.engine) as conn:
            return [(row[0], stored_chunk(row[1:])) for row in conn.execute(query)]
