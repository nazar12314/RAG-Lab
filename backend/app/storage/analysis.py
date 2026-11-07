"""Read-only PostgreSQL queries for the Data Analysis module.

Reads only retriever-facing schemas (corpus, search, graph). Gold labels in `eval` are
deliberately out of reach: the explorer shows what retrievers can see.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Engine, text

Row = dict[str, Any]


def _rows(engine: Engine, sql: str, **params: Any) -> list[Row]:
    with engine.connect() as conn:
        return [dict(r._mapping) for r in conn.execute(text(sql), params)]


class PostgresAnalysisSource:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def dataset_versions(self) -> list[Row]:
        return _rows(self.engine, "SELECT * FROM corpus.dataset_versions ORDER BY id")

    def graph_versions(self, dataset: str) -> list[Row]:
        return _rows(
            self.engine,
            "SELECT id, kind, created_at FROM graph.graph_versions "
            "WHERE dataset_version_id = :dataset ORDER BY kind, id",
            dataset=dataset,
        )

    def index_profiles(self, dataset: str) -> list[Row]:
        return _rows(
            self.engine,
            "SELECT id, status, chunker, chunk_count FROM search.index_profiles "
            "WHERE dataset_version_id = :dataset ORDER BY id",
            dataset=dataset,
        )

    def snapshot_rows(self, graph: str) -> dict[str, list[Row]]:
        """Everything needed for the cached analysis snapshot; document bodies included once."""
        e = self.engine
        return {
            "subsystems": _rows(e, "SELECT * FROM corpus.subsystems"),
            "teams": _rows(e, "SELECT * FROM corpus.teams"),
            "external_systems": _rows(e, "SELECT * FROM corpus.external_systems"),
            "services": _rows(e, "SELECT * FROM corpus.services"),
            "service_dependencies": _rows(e, "SELECT * FROM corpus.service_dependencies"),
            "deployments": _rows(e, "SELECT * FROM corpus.deployments"),
            "incidents": _rows(e, "SELECT * FROM corpus.incidents"),
            "incident_services": _rows(e, "SELECT * FROM corpus.incident_services"),
            "incident_deployments": _rows(e, "SELECT * FROM corpus.incident_deployments"),
            "documents": _rows(
                e,
                "SELECT id, title, doc_type, created_at, author, source_uri, content, "
                "content_hash, metadata FROM corpus.documents",
            ),
            "entities": _rows(
                e,
                "SELECT key, entity_type, canonical_name, external_ref FROM graph.entities "
                "WHERE graph_version_id = :graph",
                graph=graph,
            ),
            "entity_aliases": _rows(
                e,
                "SELECT e.key AS entity_key, a.alias FROM graph.entity_aliases a "
                "JOIN graph.entities e ON e.id = a.entity_id WHERE e.graph_version_id = :graph",
                graph=graph,
            ),
            "relations": _rows(
                e,
                "SELECT r.key AS id, s.key AS source_key, t.key AS target_key, r.relation_type, "
                "r.confidence, r.verified_status, r.valid_from, r.valid_to "
                "FROM graph.relations r "
                "JOIN graph.entities s ON s.id = r.source_entity_id "
                "JOIN graph.entities t ON t.id = r.target_entity_id "
                "WHERE r.graph_version_id = :graph",
                graph=graph,
            ),
            "relation_evidence": _rows(
                e,
                "SELECT r.key AS relation_id, ev.evidence_kind, ev.document_id, ev.span_start, "
                "ev.span_end, ev.record_table, ev.record_id "
                "FROM graph.relation_evidence ev JOIN graph.relations r ON r.id = ev.relation_id "
                "WHERE r.graph_version_id = :graph",
                graph=graph,
            ),
        }

    def search_document_ids(self, query: str) -> set[str]:
        pattern = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        rows = _rows(
            self.engine,
            "SELECT id FROM corpus.documents WHERE content ILIKE :p OR title ILIKE :p",
            p=pattern,
        )
        return {r["id"] for r in rows}

    def chunks(self, index_profile: str, document_id: str) -> list[Row]:
        return _rows(
            self.engine,
            "SELECT id, ordinal, span_start, span_end, token_count, "
            "embedding IS NOT NULL AS has_embedding FROM search.document_chunks "
            "WHERE index_profile_id = :profile AND document_id = :doc ORDER BY ordinal",
            profile=index_profile,
            doc=document_id,
        )
