"""Benchmark questions: authored in questions.yaml, validated against facts and the graph."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from backend.app.dataset.canonical import Canonical
from backend.app.dataset.facts import Fact

Row = dict[str, Any]

SPLITS = {"showcase": 20, "development": 30, "heldout": 30}
CATEGORIES = {
    "exact_id",
    "lexical",
    "semantic",
    "direct_relationship",
    "multi_hop",
    "temporal",
    "aggregate",
    "mixed",
    "unanswerable",
}
ANSWER_TYPES = {"text", "entity", "entity_list", "count", "date", "boolean", "abstain"}
TOOLS = {
    "exact_lookup",
    "keyword_search",
    "semantic_search",
    "graph_traverse",
    "aggregate_records",
    "fetch_evidence",
}


def build_benchmark(
    path: Path,
    c: Canonical,
    facts: list[Fact],
    fact_sources: list[Row],
    graph: dict[str, list[Row]],
    document_ids: set[str],
) -> tuple[dict[str, list[Row]], list[str]]:
    if not path.exists():
        return {}, [f"{path.name} not found"]
    raw = yaml.safe_load(path.read_text())["questions"]
    fact_ids = {f.id for f in facts}
    supported = {s["fact_id"] for s in fact_sources if s["stance"] == "supports"}
    verified_edges = {
        (r["source_key"], r["relation_type"], r["target_key"])
        for r in graph["relations"]
        if r["verified_status"] == "verified"
    }
    entity_keys = {e["key"] for e in graph["entities"]}

    errors: list[str] = []
    questions, evidence, documents, paths, tools = [], [], [], [], []
    seen: set[str] = set()
    for q in raw:
        qid = q["id"]
        if qid in seen:
            errors.append(f"{qid}: duplicate id")
        seen.add(qid)
        if q["split"] not in SPLITS:
            errors.append(f"{qid}: unknown split {q['split']}")
        if q["category"] not in CATEGORIES:
            errors.append(f"{qid}: unknown category {q['category']}")
        if q["answer_type"] not in ANSWER_TYPES:
            errors.append(f"{qid}: unknown answer_type {q['answer_type']}")
        answerable = q.get("answerable", True)
        required = q.get("required_facts", [])
        # Document-finding questions ("which runbooks cover X") are judged on whole documents.
        acceptable_docs = q.get("acceptable_documents", [])
        if answerable and not (required or acceptable_docs):
            errors.append(f"{qid}: answerable question without required facts or documents")
        for doc_id in acceptable_docs:
            if doc_id not in document_ids:
                errors.append(f"{qid}: unknown document {doc_id}")
            documents.append({"question_id": qid, "document_id": doc_id})
        if not answerable and q["answer_type"] != "abstain":
            errors.append(f"{qid}: unanswerable question must use answer_type abstain")
        for level in ("required_facts", "supporting_facts"):
            for fid in q.get(level, []):
                if fid not in fact_ids:
                    errors.append(f"{qid}: unknown fact {fid}")
                elif fid not in supported:
                    errors.append(f"{qid}: fact {fid} has no supporting source")
                evidence.append(
                    {
                        "question_id": qid,
                        "fact_id": fid,
                        "requirement": level.removesuffix("_facts"),
                    }
                )
        for p_index, path_steps in enumerate(q.get("expected_paths", [])):
            for s_index, (src, rel, dst) in enumerate(path_steps):
                if src not in entity_keys or dst not in entity_keys:
                    errors.append(f"{qid}: unknown entity in path step {src} {rel} {dst}")
                elif (src, rel, dst) not in verified_edges:
                    errors.append(f"{qid}: path step not in curated graph: {src} {rel} {dst}")
                if s_index and path_steps[s_index - 1][2] != src:
                    errors.append(f"{qid}: path {p_index} is not a connected chain")
                paths.append(
                    {
                        "question_id": qid,
                        "path_index": p_index,
                        "step_index": s_index,
                        "source_key": src,
                        "relation_type": rel,
                        "target_key": dst,
                    }
                )
        first = set(q.get("first_tools", []))
        for tool in q.get("suggested_tools", []):
            if tool not in TOOLS:
                errors.append(f"{qid}: unknown tool {tool}")
            tools.append({"question_id": qid, "tool_name": tool, "is_first_tool": tool in first})
        if not first <= set(q.get("suggested_tools", [])):
            errors.append(f"{qid}: first_tools must be a subset of suggested_tools")
        questions.append(
            {
                "id": qid,
                "split": q["split"],
                "category": q["category"],
                "question": q["question"].strip(),
                "reference_answer": q["reference_answer"].strip(),
                "accepted_answers": q.get("accepted_answers", []),
                "answer_type": q["answer_type"],
                "answerable": answerable,
                "as_of": q.get("as_of", c.as_of.isoformat()),
                "notes": q.get("notes"),
            }
        )

    split_counts = Counter(q["split"] for q in questions)
    for split, expected in SPLITS.items():
        if split_counts[split] != expected:
            errors.append(f"split {split}: {split_counts[split]} questions, expected {expected}")
    for split in SPLITS:
        cats = {q["category"] for q in questions if q["split"] == split}
        if split_counts[split] and cats != CATEGORIES:
            errors.append(f"split {split} misses categories {sorted(CATEGORIES - cats)}")

    tables = {
        "questions": questions,
        "question_evidence": evidence,
        "question_documents": documents,
        "question_paths": paths,
        "question_tools": tools,
    }
    return tables, errors
