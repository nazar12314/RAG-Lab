"""Every registered ranked retriever must honour the same evidence contract."""

import pytest

from backend.app.models.contracts import RetrievalRequest
from backend.app.retrieval.registry import build_retrievers
from tests.retrieval_fakes import FakeEmbedder, FakeStore, make_profile

STRATEGIES = list(build_retrievers(FakeStore(), lambda model: FakeEmbedder()))


@pytest.fixture(params=STRATEGIES)
def retriever(request):
    return build_retrievers(FakeStore(), lambda model: FakeEmbedder())[request.param]


def run(retriever, top_k=5):
    # The question shares terms with every sample chunk, so keyword search matches them all.
    question = "pool maintenance connection customers requests"
    return retriever.retrieve(
        RetrievalRequest(question=question, index=make_profile(), top_k=top_k)
    )


def test_ranks_are_consecutive_and_scores_descend(retriever):
    evidence = run(retriever).evidence
    assert [e.rank for e in evidence] == list(range(1, len(evidence) + 1))
    assert [e.score for e in evidence] == sorted((e.score for e in evidence), reverse=True)


def test_top_k_is_respected(retriever):
    assert len(run(retriever, top_k=2).evidence) == 2


def test_evidence_ids_point_at_source_spans(retriever):
    for item in run(retriever).evidence:
        assert item.evidence_id == f"{item.document_id}:{item.span_start}-{item.span_end}"
        assert item.document_title and item.source_uri and item.text


def test_repeated_runs_are_deterministic(retriever):
    assert run(retriever).evidence == run(retriever).evidence


def test_strategies_are_described_for_the_ui(retriever):
    assert retriever.label and retriever.description
