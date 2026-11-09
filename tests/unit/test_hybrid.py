import pytest

from backend.app.models.contracts import Evidence, RetrievalRequest, RetrievalResult, Usage
from backend.app.retrieval.base import ProviderError
from backend.app.retrieval.hybrid import MIN_DEPTH, RRF_K, HybridRetriever, fuse
from tests.retrieval_fakes import BUILT_AT, make_profile


def item(document_id: str, rank: int, terms: list[str] | None = None) -> Evidence:
    return Evidence(
        document_id=document_id,
        document_title=document_id,
        doc_type="runbook",
        source_uri="x",
        created_at=BUILT_AT,
        section_path=None,
        text="body",
        span_start=0,
        span_end=4,
        rank=rank,
        score=100.0 - rank,
        matched_terms=terms or [],
    )


def test_score_is_the_sum_of_reciprocal_ranks():
    fused = fuse({"a": [item("X", 1)], "b": [item("Y", 1), item("X", 3)]}, top_k=2)
    assert fused[0].document_id == "X"
    assert fused[0].score == pytest.approx(1 / (RRF_K + 1) + 1 / (RRF_K + 3))
    assert fused[1].score == pytest.approx(1 / (RRF_K + 1))


def test_agreement_beats_a_single_high_rank():
    rankings = {
        "a": [item("ONLY-A", 1), item("BOTH", 4)],
        "b": [item("ONLY-B", 1), item("BOTH", 4)],
    }
    assert fuse(rankings, top_k=1)[0].document_id == "BOTH"


def test_component_scales_do_not_matter():
    small = {"a": [item("X", 1).model_copy(update={"score": 0.001})]}
    large = {"a": [item("X", 1).model_copy(update={"score": 900.0})]}
    assert fuse(small, 1)[0].score == fuse(large, 1)[0].score


def test_results_are_reranked_and_explain_their_sources():
    fused = fuse({"bm25": [item("X", 7, ["pool"])], "vector": [item("X", 2)]}, top_k=5)
    assert [e.rank for e in fused] == [1]
    assert fused[0].rank_details == {"bm25": 7, "vector": 2}
    assert fused[0].matched_terms == ["pool"]


def test_matched_terms_survive_when_the_keyword_side_comes_second():
    fused = fuse({"vector": [item("X", 1)], "bm25": [item("X", 2, ["pool"])]}, top_k=1)
    assert fused[0].matched_terms == ["pool"]


def test_ties_are_deterministic():
    rankings = {"a": [item("B", 1)], "b": [item("A", 1)]}
    assert [e.document_id for e in fuse(rankings, 2)] == ["A", "B"]


class Stub:
    label = description = "stub"

    def __init__(self, evidence: list[Evidence], tokens: int = 0) -> None:
        self.evidence = evidence
        self.tokens = tokens
        self.requests: list[RetrievalRequest] = []

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        self.requests.append(request)
        return RetrievalResult(
            evidence=self.evidence,
            usage=Usage(embedding_tokens=self.tokens),
            metadata={"name": "stub"},
        )


def request(top_k: int = 5) -> RetrievalRequest:
    return RetrievalRequest(question="q", index=make_profile(), top_k=top_k)


def test_components_search_deeper_than_top_k():
    left, right = Stub([item("X", 1)]), Stub([item("Y", 1)])
    HybridRetriever({"a": left, "b": right}).retrieve(request(top_k=3))
    assert left.requests[0].top_k == right.requests[0].top_k == MIN_DEPTH


def test_usage_and_component_metadata_are_reported():
    retriever = HybridRetriever({"a": Stub([], tokens=2), "b": Stub([], tokens=5)})
    result = retriever.retrieve(request())
    assert result.usage.embedding_tokens == 7
    assert set(result.metadata["components"]) == {"a", "b"}


def test_a_failing_component_is_not_silently_ignored():
    class Failing(Stub):
        def retrieve(self, request):
            raise ProviderError("down")

    with pytest.raises(ProviderError):
        HybridRetriever({"a": Stub([]), "b": Failing([])}).retrieve(request())
