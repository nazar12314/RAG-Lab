"""Builds the seed dataset and gold labels from the canonical model.

Usage: python -m backend.app.dataset.build [--check]

Outputs are deterministic and committed, so a classroom setup can seed without rebuilding.
`--check` rebuilds in memory and fails if the committed files differ.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from backend.app.dataset.benchmark import build_benchmark
from backend.app.dataset.canonical import load_canonical
from backend.app.dataset.documents import DocumentFactory
from backend.app.dataset.facts import build_facts
from backend.app.dataset.graph import build_curated_graph
from backend.app.dataset.records import build_records, record_fact_sources
from backend.app.dataset.validate import DatasetError, validate_artifacts, validate_canonical

DATASET_VERSION = "engineering-ops-v1"
REPO_ROOT = Path(__file__).resolve().parents[3]
SEED_DIR = REPO_ROOT / "data" / "seed" / DATASET_VERSION
BENCHMARK_DIR = REPO_ROOT / "data" / "benchmark" / DATASET_VERSION


def jsonl(rows: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def build(seed_dir: Path = SEED_DIR, benchmark_dir: Path = BENCHMARK_DIR) -> dict[Path, str]:
    """Returns {output path: file content} without touching the filesystem."""
    c = load_canonical(seed_dir / "canonical")
    errors = validate_canonical(c)
    if errors:
        raise DatasetError("canonical model is inconsistent:\n" + "\n".join(errors))

    records = build_records(c)
    documents = DocumentFactory(c).all_documents()
    facts = build_facts(c)

    doc_sources = [
        {
            "fact_id": m.fact_id,
            "source_kind": "document",
            "document_id": d.id,
            "span_start": m.start,
            "span_end": m.end,
            "stance": m.stance,
        }
        for d in documents
        for m in d.facts
    ]
    fact_sources = record_fact_sources(c, records) + doc_sources
    supporting_spans: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for s in doc_sources:
        if s["stance"] == "supports":
            supporting_spans[s["fact_id"]].append(s)

    graph, relation_facts = build_curated_graph(c, supporting_spans)
    errors = validate_artifacts(
        {f.id for f in facts},
        documents,
        fact_sources,
        graph["relations"],
        graph["relation_evidence"],
    )
    benchmark, bench_errors = build_benchmark(
        benchmark_dir / "questions.yaml",
        c,
        facts,
        fact_sources,
        graph,
        {d.id for d in documents},
    )
    errors += bench_errors
    if errors:
        raise DatasetError("generated artifacts are inconsistent:\n" + "\n".join(errors))

    records["documents"] = [
        {
            "id": d.id,
            "title": d.title,
            "doc_type": d.doc_type,
            "created_at": d.created_at.isoformat(),
            "author": d.author,
            "source_uri": d.source_uri,
            "content": d.content,
            "content_hash": sha256(d.content),
            "metadata": d.metadata,
        }
        for d in documents
    ]

    out: dict[Path, str] = {}
    corpus = seed_dir / "corpus"
    for table, rows in records.items():
        out[corpus / f"{table}.jsonl"] = jsonl(rows)
    for d in documents:
        out[corpus / "documents" / f"{d.id}.md"] = d.content
    for table, rows in graph.items():
        out[seed_dir / "graph" / "curated" / f"{table}.jsonl"] = jsonl(rows)

    out[benchmark_dir / "facts.jsonl"] = jsonl([f.__dict__ for f in facts])
    out[benchmark_dir / "fact_sources.jsonl"] = jsonl(fact_sources)
    out[benchmark_dir / "entity_mentions.jsonl"] = jsonl(
        [
            {
                "document_id": d.id,
                "entity_key": m.entity_id,
                "span_start": m.start,
                "span_end": m.end,
                "surface": m.surface,
            }
            for d in documents
            for m in d.entities
        ]
    )
    out[benchmark_dir / "relation_facts.jsonl"] = jsonl(relation_facts)
    for name, rows in benchmark.items():
        out[benchmark_dir / f"{name}.jsonl"] = jsonl(rows)

    manifest = {
        "dataset_version": DATASET_VERSION,
        "company": c.company,
        "as_of": c.as_of.isoformat(),
        "period": {"start": c.period_start.isoformat(), "end": c.period_end.isoformat()},
        "counts": {
            **{t: len(r) for t, r in records.items()},
            **{f"graph_curated.{t}": len(r) for t, r in graph.items()},
            "facts": len(facts),
            **{f"benchmark.{t}": len(r) for t, r in benchmark.items()},
        },
        "documents_by_type": dict(sorted(Counter(d.doc_type for d in documents).items())),
        "relations_by_type": dict(
            sorted(Counter(r["relation_type"] for r in graph["relations"]).items())
        ),
        "corpus_hash": sha256("".join(out[p] for p in sorted(out) if p.is_relative_to(corpus))),
    }
    out[seed_dir / "manifest.json"] = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if committed files are stale")
    args = parser.parse_args()
    try:
        outputs = build()
    except DatasetError as exc:
        print(exc, file=sys.stderr)
        return 1

    managed = [SEED_DIR / "corpus", SEED_DIR / "graph"]
    existing = {p for root in managed for p in root.rglob("*") if p.is_file()}
    stale = existing - set(outputs)

    if args.check:
        diff = [p for p, text in outputs.items() if not p.exists() or p.read_text() != text]
        diff += sorted(stale)
        for p in diff:
            print(f"out of date: {p.relative_to(REPO_ROOT)}", file=sys.stderr)
        return 1 if diff else 0

    for p in stale:
        p.unlink()
    for path, text in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    manifest = json.loads(outputs[SEED_DIR / "manifest.json"])
    print(json.dumps(manifest["counts"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
