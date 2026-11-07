import json

import pytest
from fastapi.testclient import TestClient

from backend.app.api.analysis import get_analysis_service
from backend.app.dataset.build import SEED_DIR
from backend.app.main import create_app
from backend.app.services.analysis_service import AnalysisService
from tests.support import SeedFileAnalysisSource

DATASET = {"dataset": "engineering-ops-v1"}


def make_client(source: SeedFileAnalysisSource) -> TestClient:
    app = create_app()
    service = AnalysisService(source)
    app.dependency_overrides[get_analysis_service] = lambda: service
    return TestClient(app)


@pytest.fixture(scope="module")
def source():
    return SeedFileAnalysisSource()


@pytest.fixture(scope="module")
def client(source):
    return make_client(source)


def manifest_counts():
    return json.loads((SEED_DIR / "manifest.json").read_text())["counts"]


def test_overview_counts_match_the_dataset(client):
    body = client.get("/analysis/overview", params=DATASET).json()
    cards = {c["id"]: c for c in body["cards"]}
    counts = manifest_counts()
    assert cards["documents"]["value"] == counts["documents"]
    assert cards["incidents"]["value"] == counts["incidents"]
    assert cards["relations"]["value"] == counts["graph_curated.relations"]
    assert cards["chunks"]["value"] == "not indexed"

    charts = {c["id"]: c for c in body["charts"]}
    assert sum(r["count"] for r in charts["doc_types"]["rows"]) == counts["documents"]
    assert sum(r["count"] for r in charts["incident_severity"]["rows"]) == counts["incidents"]
    assert all(c["click"] and c["record_type"] for c in body["charts"])


def test_charts_ignore_their_own_dimension(client):
    params = {**DATASET, "doc_type": "postmortem"}
    charts = {c["id"]: c for c in client.get("/analysis/overview", params=params).json()["charts"]}
    assert len(charts["doc_types"]["rows"]) > 1
    lengths = sum(r["count"] for r in charts["doc_length"]["rows"])
    assert lengths == 16


def test_records_filtering_and_applied_filters(client):
    params = {
        **DATASET,
        "record_type": "incidents",
        "service": "SVC-PAYMENTS-API",
        "severity": [1],
        "doc_type": "runbook",
    }
    page = client.get("/analysis/records", params=params).json()
    assert [i["id"] for i in page["items"]] == ["INC-104", "INC-113", "INC-123"]
    assert page["applied_filters"] == ["service", "severities"]
    assert page["ignored_filters"] == ["doc_types"]
    assert page["unfiltered_total"] == 38


def test_text_search_covers_document_content(client):
    params = {**DATASET, "record_type": "documents", "q": "PAYMENTS_DB_POOL_MAX"}
    ids = {i["id"] for i in client.get("/analysis/records", params=params).json()["items"]}
    assert {"DOC-PM-INC-104", "DOC-RB-PAYMENTS-API"} <= ids


def test_relation_filters_keep_direction(client):
    params = {
        **DATASET,
        "record_type": "relations",
        "relation_type": "DEPENDS_ON",
        "service": "SVC-PAYMENTS-API",
        "limit": 200,
    }
    items = client.get("/analysis/records", params=params).json()["items"]
    outgoing = {i["target_key"] for i in items if i["source_key"] == "SVC-PAYMENTS-API"}
    incoming = {i["source_key"] for i in items if i["target_key"] == "SVC-PAYMENTS-API"}
    assert {"SVC-PSP-ADAPTER", "SVC-FRAUD-SERVICE", "SVC-ORDERS-DB"} <= outgoing
    assert incoming == {"SVC-CHECKOUT-API"}


def test_validity_filter_on_dependencies(client):
    params = {
        **DATASET,
        "record_type": "dependencies",
        "service": "SVC-FRAUD-SERVICE",
        "date_from": "2026-05-01",
        "date_to": "2026-05-31",
    }
    items = client.get("/analysis/records", params=params).json()["items"]
    assert {i["id"] for i in items} == {"LINK-10", "LINK-33"}


def test_pagination_and_sorting(client):
    params = {
        **DATASET,
        "record_type": "deployments",
        "limit": 10,
        "offset": 80,
        "sort": "deployed_at",
    }
    page = client.get("/analysis/records", params=params).json()
    assert page["total"] == 87 and len(page["items"]) == 7
    assert page["items"][-1]["id"] == "DPL-087"
    too_big = client.get("/analysis/records", params={**params, "limit": 1000})
    assert too_big.status_code == 422


def test_edge_detail_links_back_to_the_supporting_sentence(client):
    trigger = next(
        i
        for i in client.get(
            "/analysis/records",
            params={
                **DATASET,
                "record_type": "relations",
                "relation_type": "TRIGGERED_BY",
                "limit": 200,
            },
        ).json()["items"]
        if i["source_key"] == "INC-104"
    )
    detail = client.get(f"/analysis/records/relations/{trigger['id']}", params=DATASET).json()
    assert detail["label"].startswith("INC-104 ")
    assert detail["label"].endswith("--TRIGGERED_BY--> Payments API v2.8.0")
    assert detail["attributes"]["direction"] == "INC-104 -> DPL-010"
    snippet = detail["evidence"][0]
    doc = client.get(f"/analysis/documents/{snippet['document_id']}", params=DATASET).json()
    passage = doc["content"][snippet["span_start"] : snippet["span_end"]]
    assert "2.8.0" in passage and passage.strip() == snippet["text"]
    assert any(h["relation_key"] == trigger["id"] for h in doc["highlights"])


def test_record_only_edge_says_so(client):
    detail = client.get("/analysis/records/relations/REL-0001", params=DATASET).json()
    assert detail["evidence"] == []
    assert detail["record_sources"] == [
        {"record_table": "services", "record_id": "SVC-CHECKOUT-API"}
    ]
    assert "record only" in detail["notes"][0]


def test_incident_detail_navigates_to_service_and_documents(client):
    detail = client.get("/analysis/records/incidents/INC-104", params=DATASET).json()
    groups = {g["title"]: g["links"] for g in detail["links"]}
    assert groups["Primary service (as recorded)"][0]["id"] == "SVC-PAYMENTS-API"
    assert {"DOC-PM-INC-104", "DOC-TKT-INC-104"} <= {d["id"] for d in groups["Documents"]}
    notes = {d["id"]: d["note"] for d in groups["Deployments (incident tracker)"]}
    assert notes["DPL-009"].startswith("ruled_out")


def test_tracker_conflicts_are_flagged(client):
    detail = client.get("/analysis/records/incidents/INC-137", params=DATASET).json()
    assert any("DPL-084" in n for n in detail["notes"])


def test_unknown_records_and_mismatched_snapshots(client):
    assert client.get("/analysis/records/incidents/INC-999", params=DATASET).status_code == 404
    assert client.get("/analysis/documents/DOC-NOPE", params=DATASET).status_code == 404
    bad_graph = client.get("/analysis/overview", params={**DATASET, "graph": "other-graph"})
    assert bad_graph.status_code == 400
    bad_index = client.get(
        "/analysis/documents/DOC-PM-INC-104", params={**DATASET, "index_profile": "missing"}
    )
    assert bad_index.status_code == 400


def test_empty_dataset_state():
    client = make_client(SeedFileAnalysisSource(loaded=False))
    assert client.get("/analysis/datasets").json() == []
    response = client.get("/analysis/overview", params=DATASET)
    assert response.status_code == 404
    assert "not loaded" in response.json()["detail"]


def test_export_csv(client):
    params = {**DATASET, "record_type": "incidents", "severity": [1], "format": "csv"}
    response = client.get("/analysis/export", params=params)
    assert response.status_code == 200
    assert response.headers["x-total-count"] == "4"
    lines = response.text.strip().splitlines()
    assert lines[0].startswith("id,title,severity") and len(lines) == 5


def test_snapshot_is_cached(source, client):
    calls = source.snapshot_calls
    client.get("/analysis/overview", params=DATASET)
    client.get("/analysis/records", params={**DATASET, "record_type": "services"})
    assert source.snapshot_calls == max(calls, 1)
