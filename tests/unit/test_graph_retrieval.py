import pytest

from backend.app.generation.answer import format_sources
from backend.app.models.contracts import RetrievalRequest
from backend.app.retrieval.base import Unsupported
from backend.app.retrieval.graph import GraphRetriever, link_entities
from backend.app.storage.graph import GraphEntity
from tests.retrieval_fakes import (
    SAMPLE_CHUNKS,
    FakeGraphStore,
    make_edge,
    make_profile,
)

CHECKOUT = GraphEntity("SVC-CHECKOUT", "Checkout API", "service")
CHECKOUT_DB = GraphEntity("SVC-CHECKOUT-DB", "Checkout DB", "service")
INC_1 = GraphEntity("INC-1", "INC-1", "incident")
INC_10 = GraphEntity("INC-10", "INC-10", "incident")


def request(question="pool", top_k=5, hops=2):
    return RetrievalRequest(question=question, index=make_profile(), top_k=top_k, hop_limit=hops)


def keys(links):
    return [link.entity.key for link in links]


def test_longest_alias_claims_the_span():
    matches = [("checkout", CHECKOUT), ("checkout db", CHECKOUT_DB)]
    assert keys(link_entities("Is the Checkout DB down?", matches)) == ["SVC-CHECKOUT-DB"]


def test_aliases_match_whole_words_only():
    assert keys(link_entities("see inc-10 now", [("inc-1", INC_1), ("inc-10", INC_10)])) == [
        "INC-10"
    ]
    assert link_entities("the checkouts failed", [("checkout", CHECKOUT)]) == []


def test_several_mentions_are_all_linked():
    links = link_entities("Did INC-1 hit Checkout?", [("inc-1", INC_1), ("checkout", CHECKOUT)])
    assert set(keys(links)) == {"INC-1", "SVC-CHECKOUT"}


def test_an_ambiguous_alias_keeps_every_entity():
    first = GraphEntity("SVC-A", "Warehouse Sync", "service")
    second = GraphEntity("SVC-B", "Warehouse Loader", "service")
    links = link_entities("the warehouse failed", [("warehouse", first), ("warehouse", second)])
    assert set(keys(links)) == {"SVC-A", "SVC-B"}


def test_question_without_an_entity_is_unsupported():
    with pytest.raises(Unsupported, match="No known entity"):
        GraphRetriever(FakeGraphStore()).retrieve(request("nothing relevant"))


def test_missing_graph_is_unsupported():
    with pytest.raises(Unsupported, match="No curated graph"):
        GraphRetriever(FakeGraphStore(version=None)).retrieve(request())


def test_seeds_and_hop_limit_reach_the_store():
    store = FakeGraphStore()
    GraphRetriever(store).retrieve(request(hops=3))
    assert store.walk_calls == [(["SVC-POOL"], 3)]


def test_closer_evidence_outranks_more_distant_evidence():
    store = FakeGraphStore(
        walks=[(1,), (2, 3)],
        evidence=[(3, SAMPLE_CHUNKS[0]), (1, SAMPLE_CHUNKS[1])],
    )
    # SAMPLE_CHUNKS[0] shares "connection" with the question but is two hops away.
    assert [e.document_id for e in GraphRetriever(store).retrieve(request()).evidence] == [
        "DOC-2",
        "DOC-1",
    ]


def test_question_relevance_breaks_equal_distance():
    store = FakeGraphStore(
        walks=[(1,), (2,)], evidence=[(1, SAMPLE_CHUNKS[1]), (2, SAMPLE_CHUNKS[0])]
    )
    evidence = GraphRetriever(store).retrieve(request("pool connection exhaustion")).evidence
    assert evidence[0].document_id == "DOC-1"


def test_refuted_edges_are_ranked_lower_and_flagged():
    edges = {1: make_edge(1, status="refuted"), 2: make_edge(2)}
    store = FakeGraphStore(
        walks=[(1,), (2,)],
        edges=edges,
        evidence=[(1, SAMPLE_CHUNKS[0]), (2, SAMPLE_CHUNKS[1])],
    )
    result = GraphRetriever(store).retrieve(request())
    assert result.evidence[0].document_id == "DOC-2"
    assert result.evidence[1].supports == ["A1 -DEPENDS_ON-> B1 [refuted]"]
    assert any(path.refuted for path in result.graph_paths)


def test_chunk_backing_several_edges_is_returned_once():
    store = FakeGraphStore(
        walks=[(1,), (2,)], evidence=[(1, SAMPLE_CHUNKS[0]), (2, SAMPLE_CHUNKS[0])]
    )
    evidence = GraphRetriever(store).retrieve(request()).evidence
    assert len(evidence) == 1
    assert len(evidence[0].supports) == 2


def test_paths_are_returned_with_their_steps():
    result = GraphRetriever(FakeGraphStore()).retrieve(request())
    assert result.graph_paths[0].hops == 2
    assert result.graph_paths[0].steps == [
        "A1 -DEPENDS_ON-> B1",
        "A3 -DEPENDS_ON-> B3",
    ]
    assert result.entities[0].key == "SVC-POOL"


def test_only_paths_backed_by_selected_evidence_are_shown():
    result = GraphRetriever(FakeGraphStore()).retrieve(request(top_k=1))
    selected = set(result.evidence[0].supports)
    assert all(set(path.steps) <= selected for path in result.graph_paths)


def test_entity_with_no_edges_returns_no_evidence():
    result = GraphRetriever(FakeGraphStore(walks=[])).retrieve(request())
    assert result.evidence == [] and result.entities[0].key == "SVC-POOL"


def test_edge_with_no_document_support_yields_no_evidence():
    result = GraphRetriever(FakeGraphStore(evidence=[])).retrieve(request())
    assert result.evidence == []


def test_graph_facts_reach_the_answer_prompt():
    evidence = GraphRetriever(FakeGraphStore()).retrieve(request()).evidence
    assert "Graph facts: A" in format_sources(evidence)
