"""One shared selection state for charts, tables and detail panels (st.session_state)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import streamlit as st

VIEWS = ["Overview", "Records & Documents", "Graph Explorer"]
RECORD_TYPES = [
    "documents",
    "incidents",
    "services",
    "deployments",
    "dependencies",
    "entities",
    "relations",
]
RECORD_LABELS = {
    "documents": "Documents",
    "incidents": "Incidents",
    "services": "Services",
    "deployments": "Deployments",
    "dependencies": "Dependencies",
    "entities": "Entities",
    "relations": "Relations",
}
SEVERITY_LABELS = {1: "SEV1", 2: "SEV2", 3: "SEV3", 4: "SEV4"}

# Widget keys for filters that have a visible control.
SERVICE, DOC_TYPES, SEVERITIES = "f_service", "f_doc_types", "f_severities"
ENTITY_TYPES, RELATION_TYPES, DATES, QUERY = "f_entity_types", "f_relation_types", "f_dates", "f_q"
# Filters only set by chart clicks; shown as removable chips.
LENGTH, EVIDENCE = "f_length", "f_evidence"

MULTI = {
    "doc_types": DOC_TYPES,
    "severities": SEVERITIES,
    "entity_types": ENTITY_TYPES,
    "relation_types": RELATION_TYPES,
}


def init(facets: dict[str, Any]) -> None:
    defaults = {
        SERVICE: None,
        DOC_TYPES: [],
        SEVERITIES: [],
        ENTITY_TYPES: [],
        RELATION_TYPES: [],
        DATES: date_bounds(facets),
        QUERY: "",
        LENGTH: None,
        EVIDENCE: None,
        "da_view": VIEWS[0],
        "da_record_type": "documents",
        "da_selected": None,
        "da_history": [],
        "da_table_seen": None,
        "da_page": 1,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def date_bounds(facets: dict[str, Any]) -> tuple[date, date]:
    return date.fromisoformat(facets["date_min"]), date.fromisoformat(facets["date_max"])


def api_filters(facets: dict[str, Any]) -> dict[str, Any]:
    ss = st.session_state
    params: dict[str, Any] = {
        "service": ss[SERVICE],
        "doc_type": ss[DOC_TYPES],
        "severity": ss[SEVERITIES],
        "entity_type": ss[ENTITY_TYPES],
        "relation_type": ss[RELATION_TYPES],
        "q": ss[QUERY].strip() or None,
        "evidence": ss[EVIDENCE],
    }
    dates = ss[DATES]
    if isinstance(dates, (tuple, list)) and len(dates) == 2 and tuple(dates) != date_bounds(facets):
        params["date_from"], params["date_to"] = dates[0], dates[1]
    if ss[LENGTH]:
        params["length_min"], params["length_max"] = ss[LENGTH]
    return params


def clear_filters(facets: dict[str, Any]) -> None:
    ss = st.session_state
    ss[SERVICE] = None
    for key in MULTI.values():
        ss[key] = []
    ss[DATES] = date_bounds(facets)
    ss[QUERY] = ""
    ss[LENGTH] = None
    ss[EVIDENCE] = None
    ss["da_page"] = 1


def _as_date(value: Any) -> date:
    if isinstance(value, (int, float)):  # Vega-Lite sends temporal values as epoch ms
        return datetime.fromtimestamp(value / 1000, tz=UTC).date()
    return date.fromisoformat(str(value)[:10])


def apply_chart_click(spec: dict[str, Any], selection: dict[str, Any], facets: dict) -> None:
    """Translate a chart selection into filters, following the chart's `click` contract."""
    if not selection:
        return
    ss = st.session_state
    click = spec["click"]
    if "week" in click and isinstance(selection, dict):
        values = selection.get("week") or []
        if len(values) == 2:
            lo, hi = sorted(_as_date(v) for v in values)
            dmin, dmax = date_bounds(facets)
            ss[DATES] = (max(lo, dmin), min(hi + timedelta(days=6), dmax))
    else:
        datum = selection[0] if isinstance(selection, list) else selection
        for field, target in click.items():
            if field not in datum:
                continue
            value = datum[field]
            if target == "service":
                ss[SERVICE] = value
            elif target in MULTI:
                ss[MULTI[target]] = [int(value) if target == "severities" else value]
            elif target == "evidence":
                ss[EVIDENCE] = value
        if "length_min" in click.values():
            ss[LENGTH] = (int(datum["bin_start"]), int(datum["bin_end"]))
    ss["da_record_type"] = spec["record_type"]
    ss["da_page"] = 1


def apply_observation(obs: dict[str, Any], facets: dict[str, Any]) -> None:
    clear_filters(facets)
    f = obs["filters"]
    ss = st.session_state
    ss[SERVICE] = f.get("service")
    ss[DOC_TYPES] = f.get("doc_types", [])
    ss[SEVERITIES] = f.get("severities", [])
    ss[ENTITY_TYPES] = f.get("entity_types", [])
    ss[RELATION_TYPES] = f.get("relation_types", [])
    ss[EVIDENCE] = f.get("evidence")
    ss["da_record_type"] = obs["record_type"]


def select(record_type: str, record_id: str, focus: tuple[int, int] | None = None) -> None:
    ss = st.session_state
    current = ss.get("da_selected")
    target = {"type": record_type, "id": record_id, "focus": focus}
    if current == target:
        return
    if current:
        ss["da_history"] = (ss["da_history"] + [current])[-20:]
    ss["da_selected"] = target


def back() -> None:
    ss = st.session_state
    if ss["da_history"]:
        ss["da_selected"] = ss["da_history"].pop()


def close_detail() -> None:
    st.session_state["da_selected"] = None
    st.session_state["da_history"] = []
