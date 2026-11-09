import json
from collections import Counter

import pytest

from backend.app.dataset.benchmark import CATEGORIES, SPLITS
from backend.app.dataset.build import BENCHMARK_DIR, SEED_DIR, build


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


@pytest.fixture(scope="module")
def outputs():
    return build()


def test_committed_artifacts_match_a_fresh_build(outputs):
    stale = [str(p) for p, text in outputs.items() if not p.exists() or p.read_text() != text]
    assert stale == [], "run `make dataset` and commit the result"


def test_fact_spans_quote_document_text():
    docs = {d["id"]: d["content"] for d in read_jsonl(SEED_DIR / "corpus" / "documents.jsonl")}
    spans = [
        s
        for s in read_jsonl(BENCHMARK_DIR / "fact_sources.jsonl")
        if s["source_kind"] == "document"
    ]
    assert spans
    for s in spans:
        assert docs[s["document_id"]][s["span_start"] : s["span_end"]].strip()

    trigger = next(s for s in spans if s["fact_id"] == "F-INC-104-TRIGGER")
    assert "2.8.0" in docs[trigger["document_id"]][trigger["span_start"] : trigger["span_end"]]


def test_retriever_facing_corpus_contains_no_gold_markup():
    for doc in read_jsonl(SEED_DIR / "corpus" / "documents.jsonl"):
        for marker in ("[[F-", "{svc:", "{dpl:", "reference_answer", "Q-0"):
            assert marker not in doc["content"], (doc["id"], marker)


def test_benchmark_splits_cover_every_category():
    questions = read_jsonl(BENCHMARK_DIR / "questions.jsonl")
    assert Counter(q["split"] for q in questions) == SPLITS
    for split in SPLITS:
        assert {q["category"] for q in questions if q["split"] == split} == CATEGORIES


def test_business_records_keep_deliberate_imperfections():
    incidents = {i["id"]: i for i in read_jsonl(SEED_DIR / "corpus" / "incidents.jsonl")}
    assert incidents["INC-131"]["primary_service_id"] == "SVC-PAYMENTS-API"

    links = {
        (r["incident_id"], r["deployment_id"]): r["association_type"]
        for r in read_jsonl(SEED_DIR / "corpus" / "incident_deployments.jsonl")
    }
    assert links[("INC-104", "DPL-010")] == "caused"
    assert links[("INC-104", "DPL-009")] == "ruled_out"
    assert links[("INC-137", "DPL-084")] == "suspected"
    assert ("INC-122", "DPL-050") not in links


def test_every_curated_relation_has_evidence():
    graph_dir = SEED_DIR / "graph" / "curated"
    relation_ids = {r["id"] for r in read_jsonl(graph_dir / "relations.jsonl")}
    evidenced = {e["relation_id"] for e in read_jsonl(graph_dir / "relation_evidence.jsonl")}
    assert relation_ids == evidenced
