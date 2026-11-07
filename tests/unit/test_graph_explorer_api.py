import pytest
from fastapi.testclient import TestClient

from backend.app.api.analysis import get_analysis_service
from backend.app.main import create_app
from backend.app.services.analysis_service import AnalysisService
from tests.support import SeedFileAnalysisSource

DATASET = {"dataset": "engineering-ops-v1"}


@pytest.fixture(scope="module")
def client():
    app = create_app()
    service = AnalysisService(SeedFileAnalysisSource())
    app.dependency_overrides[get_analysis_service] = lambda: service
    return TestClient(app)


def neighborhood(client, **params):
    response = client.get("/analysis/graph/neighborhood", params={**DATASET, **params})
    assert response.status_code == 200, response.text
    return response.json()


def edge_set(view):
    return {(e["source"], e["relation_type"], e["target"]) for e in view["edges"]}


@pytest.mark.parametrize(
    ("query", "key", "matched_on"),
    [
        ("INC-104", "INC-104", "id"),
        ("payment-service", "SVC-PAYMENTS-API", "alias"),
        ("Pricing Engine", "SVC-PRICING-SERVICE", "name"),
    ],
)
def test_search_by_id_alias_and_name(client, query, key, matched_on):
    matches = client.get("/analysis/graph/search", params={**DATASET, "q": query}).json()
    assert matches[0]["key"] == key
    assert matches[0]["matched_on"] == matched_on


def test_demo_story_is_traversable_with_direction_kept(client):
    view = neighborhood(
        client,
        node="SVC-CHECKOUT-API",
        depth=3,
        direction="out",
        relation_type=["DEPENDS_ON", "AFFECTED_BY", "TRIGGERED_BY", "RESOLVED_BY"],
        max_nodes=200,
    )
    edges = edge_set(view)
    assert ("SVC-CHECKOUT-API", "DEPENDS_ON", "SVC-PAYMENTS-API") in edges
    assert ("SVC-PAYMENTS-API", "AFFECTED_BY", "INC-104") in edges
    assert ("INC-104", "TRIGGERED_BY", "DPL-010") in edges
    assert ("INC-104", "RESOLVED_BY", "DPL-011") in edges
    depth = {n["key"]: n["depth"] for n in view["nodes"]}
    assert depth["SVC-CHECKOUT-API"] == 0 and depth["SVC-PAYMENTS-API"] == 1
    assert "outgoing only" in view["projection"]["description"]


def test_direction_filter_separates_incoming_and_outgoing(client):
    outgoing = neighborhood(
        client, node="SVC-PAYMENTS-API", relation_type=["DEPENDS_ON"], direction="out"
    )
    incoming = neighborhood(
        client, node="SVC-PAYMENTS-API", relation_type=["DEPENDS_ON"], direction="in"
    )
    assert {n["key"] for n in outgoing["nodes"]} >= {"SVC-PSP-ADAPTER", "SVC-ORDERS-DB"}
    assert {n["key"] for n in incoming["nodes"]} == {"SVC-PAYMENTS-API", "SVC-CHECKOUT-API"}


def test_validity_date_filters_historical_dependencies(client):
    before = neighborhood(
        client, node="SVC-FRAUD-SERVICE", relation_type=["DEPENDS_ON"], as_of="2026-05-01"
    )
    after = neighborhood(
        client, node="SVC-FRAUD-SERVICE", relation_type=["DEPENDS_ON"], as_of="2026-07-01"
    )
    assert ("SVC-CHECKOUT-API", "DEPENDS_ON", "SVC-FRAUD-SERVICE") in edge_set(before)
    assert ("SVC-PAYMENTS-API", "DEPENDS_ON", "SVC-FRAUD-SERVICE") not in edge_set(before)
    assert ("SVC-PAYMENTS-API", "DEPENDS_ON", "SVC-FRAUD-SERVICE") in edge_set(after)


def test_refuted_edges_are_flagged_and_can_be_hidden(client):
    shown = neighborhood(client, node="INC-104")
    refuted = [e for e in shown["edges"] if e["verified_status"] == "refuted"]
    assert [(e["relation_type"], e["target"]) for e in refuted] == [
        ("SUSPECTED_TRIGGER", "DPL-009")
    ]
    hidden = neighborhood(client, node="INC-104", include_refuted=False)
    assert all(e["verified_status"] != "refuted" for e in hidden["edges"])


def test_size_cap_reports_truncation(client):
    view = neighborhood(client, node="SVC-CHECKOUT-API", depth=3, max_nodes=30)
    assert len(view["nodes"]) == 30 and view["truncated"]
    assert view["reachable_nodes"] > 30
    assert "Reduce the depth" in view["truncation_reason"]
    keys = {n["key"] for n in view["nodes"]}
    assert all(e["source"] in keys and e["target"] in keys for e in view["edges"])


def test_expansion_adds_neighbors_and_keeps_breadcrumb(client):
    base = neighborhood(client, node="SVC-CHECKOUT-API", relation_type=["DEPENDS_ON"])
    grown = neighborhood(
        client, node="SVC-CHECKOUT-API", relation_type=["DEPENDS_ON"], expand=["SVC-PAYMENTS-API"]
    )
    added = {n["key"] for n in grown["nodes"]} - {n["key"] for n in base["nodes"]}
    assert {"SVC-PSP-ADAPTER", "SVC-LEDGER-SERVICE"} <= added
    assert grown["expanded"] == ["SVC-PAYMENTS-API"]
    assert grown["seed"] == "SVC-CHECKOUT-API"


def test_neighborhood_is_deterministic(client):
    a = neighborhood(client, node="SVC-ORDERS-DB", depth=2)
    b = neighborhood(client, node="SVC-ORDERS-DB", depth=2)
    assert [n["key"] for n in a["nodes"]] == [n["key"] for n in b["nodes"]]
    assert [e["id"] for e in a["edges"]] == [e["id"] for e in b["edges"]]


def test_paths_preserve_stored_direction(client):
    result = client.get(
        "/analysis/graph/path",
        params={
            **DATASET,
            "source": "SVC-CHECKOUT-API",
            "target": "DPL-010",
            "relation_type": ["DEPENDS_ON", "AFFECTED_BY", "TRIGGERED_BY", "DEPLOYED_TO"],
        },
    ).json()
    assert result["length"] == 2
    for path in result["paths"]:
        for step in path["steps"]:
            assert step["edges"]
            for edge in step["edges"]:
                assert {edge["source"], edge["target"]} == {step["from_key"], step["to_key"]}
    reverse = [
        e
        for p in result["paths"]
        for s in p["steps"]
        for e in s["edges"]
        if e["source"] == s["to_key"]
    ]
    assert ("DPL-010", "DEPLOYED_TO") in {(e["source"], e["relation_type"]) for e in reverse}
    assert "not proof of causality" in result["message"]


def test_directed_paths_and_missing_connections(client):
    # Teams only receive OWNED_BY edges, so nothing is reachable from a team when directed.
    params = {**DATASET, "source": "TEAM-PAYMENTS", "target": "SVC-PSP-ADAPTER"}
    directed = client.get("/analysis/graph/path", params={**params, "directed": True}).json()
    assert directed["paths"] == [] and directed["length"] is None
    undirected = client.get("/analysis/graph/path", params=params).json()
    assert undirected["length"] == 1
    refuted_only = client.get(
        "/analysis/graph/path",
        params={
            **DATASET,
            "source": "INC-104",
            "target": "DPL-009",
            "relation_type": ["SUSPECTED_TRIGGER"],
        },
    ).json()
    assert refuted_only["paths"] == []
    with_refuted = client.get(
        "/analysis/graph/path",
        params={
            **DATASET,
            "source": "INC-104",
            "target": "DPL-009",
            "relation_type": ["SUSPECTED_TRIGGER"],
            "include_refuted": True,
        },
    ).json()
    assert with_refuted["length"] == 1


def test_bad_graph_requests(client):
    assert (
        client.get("/analysis/graph/neighborhood", params={**DATASET, "node": "NOPE"}).status_code
        == 404
    )
    assert (
        client.get(
            "/analysis/graph/neighborhood", params={**DATASET, "node": "INC-104", "depth": 4}
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/analysis/graph/path", params={**DATASET, "source": "INC-104", "target": "NOPE"}
        ).status_code
        == 404
    )
