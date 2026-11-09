from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from frontend.analysis.api import LabApiError
from frontend.playground import api
from frontend.playground.views import answer_markdown, escape_markdown, snippet

SCREEN = Path(__file__).parents[2] / "frontend/screens/playground.py"
OPTIONS = {
    "dataset_version": "engineering-ops-v1",
    "strategies": [
        {"id": "bm25", "label": "BM25", "description": "Keywords"},
        {"id": "vector", "label": "Vector", "description": "Embeddings"},
    ],
    "indexes": [{"id": "test-index"}],
    "generation_available": True,
    "default_top_k": 5,
    "max_top_k": 20,
    "default_hop_limit": 2,
    "max_hops": 3,
}
EXAMPLES = [{"id": "Q-001", "category": "exact_id", "question": "What happened in INC-104?"}]


def result(strategy="bm25", **overrides):
    evidence = {
        "evidence_id": "DOC-1:0-10",
        "document_title": "Postmortem: INC-104",
        "doc_type": "postmortem",
        "created_at": "2026-04-22T00:00:00Z",
        "section_path": "Root cause",
        "text": "Pool exhausted <b>hard</b>",
        "rank": 1,
        "score": 12.5,
        "matched_terms": ["pool"],
        "rank_details": {},
        "supports": [],
    }
    answer = {
        "text": "The pool ran out [1].",
        "abstained": False,
        "citations": ["DOC-1:0-10"],
        "model": "fake-chat",
        "prompt_version": "answer-v1",
        "context_sources": 1,
    }
    return {
        "strategy": strategy,
        "status": "ok",
        "message": None,
        "top_k": 5,
        "evidence": [evidence],
        "graph_paths": [],
        "entities": [],
        "tool_trace": [],
        "metadata": {},
        "answer": answer,
        "answer_error": None,
        "latency": {"retrieval_ms": 3.0, "generation_ms": 900.0},
        "usage": {"embedding_tokens": 0, "prompt_tokens": 10, "completion_tokens": 5},
        **overrides,
    }


@pytest.fixture
def backend(monkeypatch):
    calls = {}

    def run(strategies, payload):
        calls.update(strategies=strategies, payload=payload)
        return calls["reply"]

    calls["reply"] = [result("bm25"), result("vector")]
    monkeypatch.setattr(api, "options", lambda: OPTIONS)
    monkeypatch.setattr(api, "examples", lambda: EXAMPLES)
    monkeypatch.setattr(api, "run", run)
    return calls


def page():
    return AppTest.from_file(SCREEN, default_timeout=20).run()


def press_run(app):
    app.text_area[0].set_value("What happened in INC-104?")
    return app.button[0].click().run()


def test_page_offers_examples_strategies_and_shows_no_results_yet(backend):
    app = page()
    assert not app.exception
    assert app.selectbox[0].options[0].startswith("Q-001")
    assert list(app.multiselect[0].options) == ["BM25", "Vector"]
    assert not app.subheader


def test_compare_shows_each_strategy_and_sends_the_controls(backend):
    app = press_run(page())
    assert not app.exception
    assert [s.value for s in app.subheader] == ["BM25", "Vector"]
    assert backend["strategies"] == ["bm25", "vector"]
    assert backend["payload"] == {
        "question": "What happened in INC-104?",
        "index_profile": "test-index",
        "top_k": 5,
        "hop_limit": 2,
        "generate": True,
    }


def test_evidence_is_drawn_before_the_answer(backend):
    backend["reply"] = [result()]
    values = [m.value for m in press_run(page()).markdown]
    evidence = next(i for i, v in enumerate(values) if v.startswith("**Retrieved evidence**"))
    assert evidence < values.index("**Generated answer**")


def test_chunk_text_is_escaped(backend):
    app = press_run(page())
    assert not app.exception
    html = "".join(str(element.proto) for element in app.main if element.type == "html")
    assert "<b>hard" not in html


def test_abstention_and_failed_strategies_are_visible(backend):
    abstained = dict(result()["answer"], text="Not enough evidence.", abstained=True, citations=[])
    backend["reply"] = [
        result("bm25", answer=abstained),
        result("vector", status="error", message="OpenAI failed", evidence=[], answer=None),
    ]
    app = press_run(page())
    assert any(w.value == "Not enough evidence." for w in app.warning)
    assert any(e.value == "OpenAI failed" for e in app.error)


def test_empty_question_is_not_submitted(backend):
    app = page().button[0].click().run()
    assert "strategies" not in backend
    assert any("Write a question" in w.value for w in app.warning)


def test_no_selected_strategy_is_not_submitted(backend):
    app = page()
    app.multiselect[0].set_value([])
    app = press_run(app)
    assert "strategies" not in backend
    assert any("at least one strategy" in w.value for w in app.warning)


def test_graph_paths_and_supported_edges_are_shown(backend):
    item = dict(result()["evidence"][0], supports=["A -DEPENDS_ON-> B"])
    backend["reply"] = [
        result(
            evidence=[item],
            graph_paths=[{"steps": ["A -DEPENDS_ON-> B", "B -AFFECTED_BY-> C"], "hops": 2}],
            entities=[{"name": "A", "entity_type": "service"}],
        )
    ]
    app = press_run(page())
    assert not app.exception
    assert any(t.value == "A -DEPENDS_ON-> B\nB -AFFECTED_BY-> C" for t in app.text)
    assert any(c.value == "Backs: A -DEPENDS_ON-> B" for c in app.caption)
    assert any(c.value == "Started from: A (service)" for c in app.caption)


def test_agent_is_opt_in_because_it_costs_more(backend, monkeypatch):
    strategies = [*OPTIONS["strategies"], {"id": "agent", "label": "Agent", "description": "LLM"}]
    monkeypatch.setattr(api, "options", lambda: {**OPTIONS, "strategies": strategies})
    assert page().multiselect[0].value == ["bm25", "vector"]


def test_agent_trace_and_undated_records_are_shown(backend, monkeypatch):
    record = dict(result()["evidence"][0], created_at=None, doc_type="record")
    call = {
        "tool": "exact_lookup",
        "args": {"record_id": "INC-104"},
        "reason": "An ID was given",
        "evidence_ids": ["incidents/INC-104"],
        "duration_ms": 4.0,
        "message": None,
    }
    backend["reply"] = [
        result("agent", evidence=[record], tool_trace=[call], metadata={"stop_reason": "answered"})
    ]
    backend_options = {
        **OPTIONS,
        "strategies": [
            *OPTIONS["strategies"],
            {"id": "agent", "label": "Agent", "description": "L"},
        ],
    }
    monkeypatch.setattr(api, "options", lambda: backend_options)
    app = press_run(page())
    assert not app.exception
    assert app.expander[0].label == "Tool trace · 1 calls · stopped: answered"
    assert any(t.value == "record_id=INC-104" for t in app.text)
    assert any(m.value.startswith("**Evidence collected**") for m in app.markdown)
    assert any("undated" in m.value for m in app.markdown)


def test_hop_control_only_applies_to_graph(backend):
    app = page()
    assert app.slider[1].disabled is True


def test_fused_ranks_are_explained(backend):
    item = dict(result()["evidence"][0], rank_details={"bm25": 2, "vector": 5})
    backend["reply"] = [result(evidence=[item])]
    app = press_run(page())
    assert any(c.value == "Ranked by: bm25 #2, vector #5" for c in app.caption)


def test_missing_index_explains_how_to_build_one(backend, monkeypatch):
    monkeypatch.setattr(api, "options", lambda: {**OPTIONS, "indexes": []})
    app = page()
    assert any("make index" in w.value for w in app.warning)
    assert not app.button


def test_backend_outage_is_reported(backend, monkeypatch):
    def down():
        raise LabApiError("Backend not reachable")

    monkeypatch.setattr(api, "options", down)
    assert page().error[0].value == "Backend not reachable"


def test_markdown_helpers():
    assert escape_markdown("a_b: [c]") == r"a\_b\: \[c\]"
    assert answer_markdown("costs $5 and $6") == r"costs \$5 and \$6"
    assert snippet("short") == "short"
    assert snippet("x" * 300, limit=10) == "x" * 10 + "…"
