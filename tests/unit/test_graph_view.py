import math

from fastapi.testclient import TestClient

from backend.app.api.analysis import get_analysis_service
from backend.app.main import create_app
from backend.app.services.analysis_service import AnalysisService
from frontend.analysis import graph_view
from tests.support import SeedFileAnalysisSource


def _client() -> TestClient:
    app = create_app()
    service = AnalysisService(SeedFileAnalysisSource())
    app.dependency_overrides[get_analysis_service] = lambda: service
    return TestClient(app)


def _view(**params):
    return (
        _client()
        .get("/analysis/graph/neighborhood", params={"dataset": "engineering-ops-v1", **params})
        .json()
    )


def test_ring_layout_puts_each_hop_on_its_own_ring():
    view = _view(node="SVC-PAYMENTS-API", depth=2, relation_type=["DEPENDS_ON"])
    pos = graph_view.ring_layout(view["nodes"], view["edges"])
    assert pos["SVC-PAYMENTS-API"] == (0.0, 0.0)
    radius = {}
    for n in view["nodes"]:
        radius.setdefault(n["depth"], set()).add(round(math.hypot(*pos[n["key"]]), 6))
    assert all(len(r) == 1 for r in radius.values())
    assert sorted(radius) == [0, 1, 2]
    assert max(radius[1]) < min(radius[2])


def test_layout_is_deterministic():
    view = _view(node="INC-104", depth=2)
    assert graph_view.ring_layout(view["nodes"], view["edges"]) == graph_view.ring_layout(
        view["nodes"], view["edges"]
    )


def test_path_layout_orders_hops_left_to_right():
    paths = [{"nodes": ["A", "B", "D"]}, {"nodes": ["A", "C", "D"]}]
    pos = graph_view.path_layout(paths)
    assert pos["A"][0] == 0 and pos["B"][0] == pos["C"][0] == 1 and pos["D"][0] == 2
    assert pos["B"][1] != pos["C"][1]


def test_arrowheads_point_along_the_stored_direction():
    nodes = [
        {
            "key": "A",
            "label": "A",
            "entity_type": "service",
            "depth": 0,
            "is_seed": True,
            "in_degree": 0,
            "out_degree": 1,
        },
        {
            "key": "B",
            "label": "B",
            "entity_type": "incident",
            "depth": 1,
            "is_seed": False,
            "in_degree": 1,
            "out_degree": 0,
        },
    ]
    edges = [
        {
            "id": "E1",
            "source": "A",
            "target": "B",
            "relation_type": "AFFECTED_BY",
            "verified_status": "verified",
            "evidence": "document",
        }
    ]
    _, right = graph_view.build_frames(nodes, edges, {"A": (0, 0), "B": (1, 0)}, set(), None)
    _, up = graph_view.build_frames(nodes, edges, {"A": (0, 0), "B": (0, 1)}, set(), None)
    assert round(right.loc[0, "angle"]) == 90  # clockwise from "up": pointing right
    assert round(up.loc[0, "angle"]) == 0
    assert right.loc[0, "ax"] < 1  # arrowhead backs off from the target node


def test_chart_has_clickable_nodes_and_edges_and_separate_color_scales():
    view = _view(node="INC-104")
    pos = graph_view.ring_layout(view["nodes"], view["edges"])
    spec = graph_view.build_chart(view["nodes"], view["edges"], pos).to_dict()
    # Altair hoists layer selections to the top-level spec.
    params = spec.get("params", []) + [
        p for layer in spec["layer"] for p in layer.get("params", [])
    ]
    names = {p["name"] for p in params}
    assert names == {graph_view.NODE_SELECTION, graph_view.EDGE_SELECTION}
    assert spec["resolve"]["scale"]["color"] == "independent"
    refuted = [e for e in view["edges"] if e["verified_status"] == "refuted"]
    assert refuted, "INC-104 has a refuted suspect edge to draw dashed"


def test_selection_parsing():
    assert graph_view.selection_of({"selection": {"node": [{"key": "INC-104"}]}}) == (
        "node",
        "INC-104",
    )
    assert graph_view.selection_of({"selection": {"edge": [{"edge_id": "REL-1"}], "node": []}}) == (
        "edge",
        "REL-1",
    )
    assert graph_view.selection_of({"selection": {}}) is None
    assert graph_view.selection_of(None) is None
