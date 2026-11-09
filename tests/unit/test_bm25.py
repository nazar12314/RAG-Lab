import math
from datetime import timedelta

import pytest

from backend.app.models.contracts import RetrievalRequest
from backend.app.retrieval.keyword import K1, B, BM25Index, BM25Retriever, tokenize
from tests.retrieval_fakes import BUILT_AT, FakeStore, make_profile


def test_identifiers_stay_whole_and_also_yield_parts():
    assert tokenize("INC-104") == ["inc-104", "inc", "104"]
    assert "payments_db_pool_max" in tokenize("PAYMENTS_DB_POOL_MAX")
    assert {"payment", "db", "pool", "max"} <= set(tokenize("PAYMENTS_DB_POOL_MAX"))


def test_stopwords_are_dropped_and_words_stemmed():
    assert tokenize("What was the exhaustion of the pools?") == ["exhaust", "pool"]
    assert tokenize("exhausted") == tokenize("exhaustion")


def test_score_matches_the_okapi_formula():
    index = BM25Index([["pool", "pool", "leak"], ["hotel"]])
    idf = math.log(1 + (2 - 1 + 0.5) / (1 + 0.5))
    average = (3 + 1) / 2
    expected = idf * 2 * (K1 + 1) / (2 + K1 * (1 - B + B * 3 / average))
    assert index.search(["pool"], 5)[0].score == pytest.approx(expected)


def test_rare_terms_outweigh_common_ones():
    documents = [["common", "rare"], *[["common", "other"]] * 20]
    assert BM25Index(documents).idf("rare") > BM25Index(documents).idf("common")
    assert BM25Index(documents).search(["common", "rare"], 1)[0].position == 0


def test_a_term_in_every_document_still_scores_positive():
    assert BM25Index([["same"], ["same"]]).idf("same") > 0


def test_longer_documents_are_penalised():
    index = BM25Index([["pool"], ["pool", *[f"filler{i}" for i in range(40)]]])
    assert [hit.position for hit in index.search(["pool"], 2)] == [0, 1]


def test_query_repetition_does_not_change_scores():
    index = BM25Index([["pool", "leak"], ["hotel"]])
    assert index.search(["pool", "pool"], 1)[0].score == index.search(["pool"], 1)[0].score


def test_ties_are_broken_deterministically():
    assert [h.position for h in BM25Index([["a"], ["a"], ["a"]]).search(["a"], 3)] == [0, 1, 2]


def test_no_shared_term_returns_nothing():
    assert BM25Index([["pool"]]).search(["missing"], 5) == []
    assert BM25Index([]).search(["pool"], 5) == []


def test_retriever_explains_what_matched():
    request = RetrievalRequest(question="pool exhaustion", index=make_profile(), top_k=5)
    result = BM25Retriever(FakeStore()).retrieve(request)
    assert result.evidence[0].document_id == "DOC-1"
    assert set(result.evidence[0].matched_terms) == {"pool", "exhaust"}
    assert result.metadata["query_terms"] == ["pool", "exhaust"]


def test_index_is_cached_until_the_profile_is_rebuilt():
    store = FakeStore()
    retriever = BM25Retriever(store)
    first = RetrievalRequest(question="pool", index=make_profile(), top_k=1)
    retriever.retrieve(first)
    retriever.retrieve(first)
    assert store.chunk_loads == 1
    rebuilt = make_profile(built_at=BUILT_AT + timedelta(hours=1))
    retriever.retrieve(RetrievalRequest(question="pool", index=rebuilt, top_k=1))
    assert store.chunk_loads == 2
