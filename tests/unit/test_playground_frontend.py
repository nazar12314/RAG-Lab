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
        "answer": answer,
        "answer_error": None,
        "latency": {"retrieval_ms": 3.0, "generation_ms": 900.0},
        "usage": {"embedding_tokens": 0, "prompt_tokens": 10, "completion_tokens": 5},
        **overrides,
    }


@pytest.fixture
def backend(monkeypatch):
    calls = {}

    def run(strategy, payload):
        calls.update(strategy=strategy, payload=payload)
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
    assert list(app.radio[0].options) == ["Compare all", "BM25", "Vector"]
    assert not app.subheader


def test_compare_shows_each_strategy_and_sends_the_controls(backend):
    app = press_run(page())
    assert not app.exception
    assert [s.value for s in app.subheader] == ["BM25", "Vector"]
    assert backend["strategy"] is None
    assert backend["payload"] == {
        "question": "What happened in INC-104?",
        "index_profile": "test-index",
        "top_k": 5,
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
    assert "strategy" not in backend
    assert any("Write a question" in w.value for w in app.warning)


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
