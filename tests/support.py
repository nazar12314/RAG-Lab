"""Test doubles shared by unit tests."""

import json
from pathlib import Path
from typing import Any

from backend.app.dataset.build import SEED_DIR

GRAPH_ID = "engineering-ops-v1-curated"


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


class SeedFileAnalysisSource:
    """AnalysisSource over the committed seed files, mirroring the PostgreSQL row shapes."""

    def __init__(self, seed_dir: Path = SEED_DIR, loaded: bool = True) -> None:
        self.seed_dir = seed_dir
        self.loaded = loaded
        self.snapshot_calls = 0
        manifest = json.loads((seed_dir / "manifest.json").read_text())
        self.dataset = {
            "id": manifest["dataset_version"],
            "company": manifest["company"],
            "as_of": manifest["as_of"],
            "period_start": manifest["period"]["start"],
            "period_end": manifest["period"]["end"],
            "corpus_hash": manifest["corpus_hash"],
            "loaded_at": "2026-11-01T00:00:00+00:00",
        }

    def dataset_versions(self) -> list[dict[str, Any]]:
        return [self.dataset] if self.loaded else []

    def graph_versions(self, dataset: str) -> list[dict[str, Any]]:
        if not self.loaded or dataset != self.dataset["id"]:
            return []
        return [{"id": GRAPH_ID, "kind": "curated", "created_at": None}]

    def index_profiles(self, dataset: str) -> list[dict[str, Any]]:
        return []

    def snapshot_rows(self, graph: str) -> dict[str, list[dict[str, Any]]]:
        self.snapshot_calls += 1
        corpus = self.seed_dir / "corpus"
        rows = {
            name: _jsonl(corpus / f"{name}.jsonl")
            for name in (
                "subsystems",
                "teams",
                "external_systems",
                "services",
                "service_dependencies",
                "deployments",
                "incidents",
                "incident_services",
                "incident_deployments",
                "documents",
            )
        }
        curated = self.seed_dir / "graph" / "curated"
        for name in ("entities", "entity_aliases", "relations", "relation_evidence"):
            rows[name] = _jsonl(curated / f"{name}.jsonl")
        return rows

    def search_document_ids(self, query: str) -> set[str]:
        needle = query.lower()
        return {
            d["id"]
            for d in _jsonl(self.seed_dir / "corpus" / "documents.jsonl")
            if needle in d["content"].lower() or needle in d["title"].lower()
        }

    def chunks(self, index_profile: str, document_id: str) -> list[dict[str, Any]]:
        return []
