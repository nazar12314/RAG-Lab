from dataclasses import replace

import pytest

from backend.app.generation.answer import format_sources
from backend.app.models.contracts import RetrievalRequest
from backend.app.retrieval.base import Unsupported
from backend.app.retrieval.graph import GraphRetriever, _walk_nodes, link_entities
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
    chain = next(path for path in result.graph_paths if path.hops == 2)
    assert chain.steps == ["A1 -DEPENDS_ON-> B1", "A3 -DEPENDS_ON-> B3"]
    assert result.entities[0].key == "SVC-POOL"


def test_paths_with_the_best_supported_edges_come_first():
    store = FakeGraphStore(
        walks=[(1,), (2,), (3, 4)],
        edges={i: make_edge(i) for i in (1, 2, 3, 4)},
        evidence=[
            (1, SAMPLE_CHUNKS[0]),
            (2, SAMPLE_CHUNKS[1]),
            (3, SAMPLE_CHUNKS[2]),
            (4, SAMPLE_CHUNKS[2]),
        ],
    )
    paths = GraphRetriever(store).retrieve(request("pool connection")).graph_paths
    assert [path.hops for path in paths] == [1, 1, 2]
    assert paths[0].steps == ["A1 -DEPENDS_ON-> B1"]


def test_a_long_weak_walk_cannot_push_out_a_strong_direct_edge():
    walks = [(1,), *[(2, i) for i in range(3, 14)]]
    edges = {i: make_edge(i) for i in range(1, 14)}
    evidence = [(1, SAMPLE_CHUNKS[0]), (2, SAMPLE_CHUNKS[1])]
    evidence += [(i, SAMPLE_CHUNKS[2]) for i in range(3, 14)]
    store = FakeGraphStore(walks=walks, edges=edges, evidence=evidence)
    paths = GraphRetriever(store).retrieve(request("pool connection")).graph_paths
    assert len(paths) == 10
    assert "A1 -DEPENDS_ON-> B1" in paths[0].steps


def test_paths_carry_typed_edges_and_the_evidence_behind_them():
    result = GraphRetriever(FakeGraphStore()).retrieve(request())
    edge = next(e for path in result.graph_paths for e in path.edges if e.id == "REL-1")
    assert (edge.source, edge.target) == ("KEY-A1", "KEY-B1")
    assert (edge.source_label, edge.source_type) == ("A1", "service")
    backing = next(item for item in result.evidence if item.document_id == "DOC-1")
    assert edge.evidence_ids == [backing.evidence_id]


def test_walk_nodes_follow_the_walk_even_against_stored_direction():
    def edge(edge_id, source, target):
        return replace(make_edge(edge_id), source_key=source, target_key=target)

    # The walk starts at SEED; both edges are stored pointing towards it.
    walk = [edge(1, "MIDDLE", "SEED"), edge(2, "FAR", "MIDDLE")]
    assert _walk_nodes(walk, {"SEED"}) == ["SEED", "MIDDLE", "FAR"]


def test_walk_nodes_prefer_the_seed_when_the_edge_points_away():
    walk = [replace(make_edge(1), source_key="SEED", target_key="NEXT")]
    assert _walk_nodes(walk, {"SEED"}) == ["SEED", "NEXT"]


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
