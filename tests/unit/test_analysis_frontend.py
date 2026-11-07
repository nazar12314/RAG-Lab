from fastapi.testclient import TestClient

from backend.app.api.analysis import get_analysis_service
from backend.app.main import create_app
from backend.app.services.analysis_service import AnalysisService
from frontend.analysis.charts import build_chart
from frontend.analysis.rendering import highlight_html, snippet_html
from tests.support import SeedFileAnalysisSource


def _highlight(start, end, status="verified"):
    return {
        "span_start": start,
        "span_end": end,
        "relation_type": "TRIGGERED_BY",
        "verified_status": status,
        "source": {"label": 'INC-1 "<b>"'},
        "target": {"label": "DPL-1"},
    }


def test_source_text_is_escaped_not_executed():
    hostile = '<script>alert(1)</script> <img src=x onerror="x()"> plain'
    out = highlight_html(hostile, [_highlight(0, 25)])
    assert "<script>" not in out and "<img" not in out
    assert "&lt;script&gt;" in out and "&lt;img src=x" in out
    assert 'title="INC-1 &quot;&lt;b&gt;&quot; --TRIGGERED_BY--&gt; DPL-1"' in out
    assert "<script>" not in snippet_html(hostile)


def test_overlapping_spans_and_focus_are_segmented():
    out = highlight_html("abcdefghij", [_highlight(0, 6), _highlight(3, 9, "refuted")], (4, 5))
    assert out.count("<mark") == 5
    assert 'class="ev focus"' in out
    assert 'class="ev refuted"' in out  # only the refuted span covers 6-9


def test_every_overview_chart_renders_with_a_click_selection():
    app = create_app()
    service = AnalysisService(SeedFileAnalysisSource())
    app.dependency_overrides[get_analysis_service] = lambda: service
    overview = (
        TestClient(app).get("/analysis/overview", params={"dataset": "engineering-ops-v1"}).json()
    )
    filters = {"doc_type": ["postmortem"], "service": "SVC-PAYMENTS-API"}
    for spec in overview["charts"]:
        chart = build_chart(spec, filters)
        assert chart is not None, spec["id"]
        params = chart.to_dict().get("params", [])
        assert any(p["name"] == "pick" for p in params), spec["id"]
