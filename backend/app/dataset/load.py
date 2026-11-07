"""Seeds PostgreSQL from the committed dataset artifacts (reset + reload in one transaction).

Usage: python -m backend.app.dataset.load [--database-url URL]

Experiment history (eval.experiment_runs / experiment_results) is preserved across reseeds.
Index profiles and chunks are dropped, because they are only valid for the corpus they were
built from; rebuild them after reseeding.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Connection, Date, DateTime, Table, insert, select, text

from backend.app.config import get_settings
from backend.app.dataset.build import BENCHMARK_DIR, SEED_DIR
from backend.app.storage.postgres import create_db_engine
from backend.app.storage.tables import corpus, eval, graph, search

CURATED_GRAPH_ID = "{dataset}-curated"

RESET_TABLES = [
    corpus.DatasetVersion,
    corpus.Subsystem,
    corpus.Team,
    corpus.ExternalSystem,
    corpus.Service,
    corpus.ServiceDependency,
    corpus.Deployment,
    corpus.Incident,
    corpus.IncidentService,
    corpus.IncidentDeployment,
    corpus.Document,
    search.IndexProfile,
    search.DocumentChunk,
    search.ChunkEntity,
    graph.GraphVersion,
    graph.Entity,
    graph.EntityAlias,
    graph.Relation,
    graph.RelationEvidence,
    eval.Fact,
    eval.FactSource,
    eval.EntityMention,
    eval.RelationFact,
    eval.Question,
    eval.QuestionEvidence,
    eval.QuestionDocument,
    eval.QuestionPath,
    eval.QuestionTool,
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def coerce(table: Table, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Converts ISO date strings and gives every row the same keys (required by executemany)."""
    keys = {key for row in rows for key in row}
    rows = [{key: row.get(key) for key in keys} for row in rows]
    converters = {}
    for col in table.columns:
        if isinstance(col.type, DateTime):
            converters[col.name] = datetime.fromisoformat
        elif isinstance(col.type, Date):
            converters[col.name] = date.fromisoformat
    out = []
    for row in rows:
        row = dict(row)
        for name, conv in converters.items():
            if row.get(name) is not None:
                row[name] = conv(row[name])
        out.append(row)
    return out


def bulk_insert(conn: Connection, model, rows: list[dict[str, Any]]) -> None:
    if rows:
        table = model.__table__
        conn.execute(insert(table), coerce(table, rows))


def load(conn: Connection, seed_dir: Path = SEED_DIR, benchmark_dir: Path = BENCHMARK_DIR) -> dict:
    manifest = json.loads((seed_dir / "manifest.json").read_text())
    dataset = manifest["dataset_version"]
    corpus_dir = seed_dir / "corpus"
    graph_dir = seed_dir / "graph" / "curated"

    names = ", ".join(f"{m.__table__.schema}.{m.__table__.name}" for m in RESET_TABLES)
    conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY"))

    bulk_insert(
        conn,
        corpus.DatasetVersion,
        [
            {
                "id": dataset,
                "company": manifest["company"],
                "as_of": manifest["as_of"],
                "period_start": manifest["period"]["start"],
                "period_end": manifest["period"]["end"],
                "corpus_hash": manifest["corpus_hash"],
                "loaded_at": datetime.now(UTC).isoformat(),
            }
        ],
    )
    for model, name in [
        (corpus.Subsystem, "subsystems"),
        (corpus.Team, "teams"),
        (corpus.ExternalSystem, "external_systems"),
        (corpus.Service, "services"),
        (corpus.ServiceDependency, "service_dependencies"),
        (corpus.Deployment, "deployments"),
        (corpus.Document, "documents"),
        (corpus.Incident, "incidents"),
        (corpus.IncidentService, "incident_services"),
        (corpus.IncidentDeployment, "incident_deployments"),
    ]:
        bulk_insert(conn, model, read_jsonl(corpus_dir / f"{name}.jsonl"))

    graph_id = CURATED_GRAPH_ID.format(dataset=dataset)
    bulk_insert(
        conn,
        graph.GraphVersion,
        [
            {
                "id": graph_id,
                "dataset_version_id": dataset,
                "kind": "curated",
                "extractor_config": {},
                "notes": "Derived from canonical facts; upper-bound baseline.",
            }
        ],
    )
    bulk_insert(
        conn,
        graph.Entity,
        [{**row, "graph_version_id": graph_id} for row in read_jsonl(graph_dir / "entities.jsonl")],
    )
    entity_ids = dict(
        conn.execute(
            select(graph.Entity.key, graph.Entity.id).where(
                graph.Entity.graph_version_id == graph_id
            )
        ).all()
    )
    bulk_insert(
        conn,
        graph.EntityAlias,
        [
            {"entity_id": entity_ids[r["entity_key"]], "alias": r["alias"]}
            for r in read_jsonl(graph_dir / "entity_aliases.jsonl")
        ],
    )
    bulk_insert(
        conn,
        graph.Relation,
        [
            {
                "graph_version_id": graph_id,
                "key": r["id"],
                "source_entity_id": entity_ids[r["source_key"]],
                "target_entity_id": entity_ids[r["target_key"]],
                "relation_type": r["relation_type"],
                "confidence": r["confidence"],
                "verified_status": r["verified_status"],
                "valid_from": r["valid_from"],
                "valid_to": r["valid_to"],
            }
            for r in read_jsonl(graph_dir / "relations.jsonl")
        ],
    )
    relation_ids = dict(
        conn.execute(
            select(graph.Relation.key, graph.Relation.id).where(
                graph.Relation.graph_version_id == graph_id
            )
        ).all()
    )
    bulk_insert(
        conn,
        graph.RelationEvidence,
        [
            {
                **{k: v for k, v in r.items() if k != "relation_id"},
                "relation_id": relation_ids[r["relation_id"]],
            }
            for r in read_jsonl(graph_dir / "relation_evidence.jsonl")
        ],
    )

    bulk_insert(conn, eval.Fact, read_jsonl(benchmark_dir / "facts.jsonl"))
    bulk_insert(conn, eval.FactSource, read_jsonl(benchmark_dir / "fact_sources.jsonl"))
    bulk_insert(conn, eval.EntityMention, read_jsonl(benchmark_dir / "entity_mentions.jsonl"))
    bulk_insert(
        conn,
        eval.RelationFact,
        [
            {"relation_id": relation_ids[r["relation_id"]], "fact_id": r["fact_id"]}
            for r in read_jsonl(benchmark_dir / "relation_facts.jsonl")
        ],
    )
    for model, name in [
        (eval.Question, "questions"),
        (eval.QuestionEvidence, "question_evidence"),
        (eval.QuestionDocument, "question_documents"),
        (eval.QuestionPath, "question_paths"),
        (eval.QuestionTool, "question_tools"),
    ]:
        bulk_insert(conn, model, read_jsonl(benchmark_dir / f"{name}.jsonl"))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()
    engine = create_db_engine(args.database_url or get_settings().database_url)
    with engine.begin() as conn:
        manifest = load(conn)
    print(f"Loaded {manifest['dataset_version']} ({manifest['corpus_hash'][:12]})")


if __name__ == "__main__":
    main()
