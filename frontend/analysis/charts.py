"""Altair charts built from backend ChartSpecs; clicks feed the shared filter state.

Colors follow the reference data-viz palette: one blue for single-series bars, an ordinal
blue ramp for severity (validated light and dark), a sequential blue for the heatmap and
the status palette (with a labeled legend) for evidence coverage.
"""

from __future__ import annotations

from typing import Any

import altair as alt
import pandas as pd

BLUE = "#2a78d6"
SEVERITY_COLORS = {"SEV1": "#184f95", "SEV2": "#2a78d6", "SEV3": "#5598e7", "SEV4": "#86b6ef"}
SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95"]
EVIDENCE_COLORS = {"document": "#0ca30c", "record_only": "#fab219", "none": "#d03b3b"}
EVIDENCE_LABELS = {
    "document": "document passage",
    "record_only": "record only",
    "none": "no source",
}
DIM_OPACITY = 0.35
SELECTION = "pick"


def _active_values(spec: dict[str, Any], filters: dict[str, Any]) -> dict[str, set]:
    """Values currently selected via filters for each clickable field of this chart."""
    mapping = {
        "service": "service",
        "doc_types": "doc_type",
        "severities": "severity",
        "entity_types": "entity_type",
        "relation_types": "relation_type",
        "evidence": "evidence",
    }
    active: dict[str, set] = {}
    for field, target in spec["click"].items():
        value = filters.get(mapping.get(target, ""))
        if value:
            active[field] = {str(v) for v in (value if isinstance(value, list) else [value])}
    if "length_min" in spec["click"].values() and filters.get("length_min") is not None:
        active["bin_start"] = {str(filters["length_min"])}
    return active


def _frame(spec: dict[str, Any], filters: dict[str, Any]) -> pd.DataFrame:
    df = pd.DataFrame(spec["rows"])
    active = _active_values(spec, filters)
    df["_active"] = True
    for field, values in active.items():
        if field in df:
            df["_active"] &= df[field].astype(str).isin(values)
    return df


def _opacity() -> alt.OpacityValue:
    return alt.condition("datum._active", alt.value(1.0), alt.value(DIM_OPACITY))


def _horizontal_bar(spec: dict, df: pd.DataFrame, tooltip: list) -> alt.Chart:
    point = alt.selection_point(name=SELECTION, fields=list(spec["click"]), on="click")
    height = max(120, 24 * len(df) + 30)
    return (
        alt.Chart(df, height=height)
        .mark_bar(color=BLUE, cornerRadiusEnd=4, height={"band": 0.7})
        .encode(
            y=alt.Y(f"{spec['x']}:N", sort="-x", title=None),
            x=alt.X(f"{spec['y']}:Q", title="count"),
            opacity=_opacity(),
            tooltip=tooltip,
        )
        .add_params(point)
    )


def build_chart(spec: dict[str, Any], filters: dict[str, Any]) -> alt.Chart | None:
    df = _frame(spec, filters)
    if df.empty:
        return None
    kind = spec["id"]

    if kind in ("doc_types", "entity_types", "relation_types"):
        return _horizontal_bar(spec, df, [spec["x"], "count"])
    if kind == "docs_by_service":
        return _horizontal_bar(spec, df, ["service", "team", "count"])

    if kind == "doc_length":
        point = alt.selection_point(name=SELECTION, fields=["bin_start", "bin_end"], on="click")
        return (
            alt.Chart(df, height=220)
            .mark_bar(color=BLUE, cornerRadiusEnd=4)
            .encode(
                x=alt.X(
                    "label:N",
                    sort=alt.SortField("bin_start"),
                    title="characters",
                    axis=alt.Axis(labelAngle=0),
                ),
                y=alt.Y("count:Q", title="documents"),
                opacity=_opacity(),
                tooltip=[alt.Tooltip("label:N", title="length"), "count"],
            )
            .add_params(point)
        )

    if kind == "incident_severity":
        point = alt.selection_point(name=SELECTION, fields=["severity"], on="click")
        return (
            alt.Chart(df, height=220)
            .mark_bar(cornerRadiusEnd=4)
            .encode(
                x=alt.X(
                    "label:N", sort=list(SEVERITY_COLORS), title=None, axis=alt.Axis(labelAngle=0)
                ),
                y=alt.Y("count:Q", title="incidents"),
                color=alt.Color(
                    "label:N",
                    legend=None,
                    scale=alt.Scale(
                        domain=list(SEVERITY_COLORS), range=list(SEVERITY_COLORS.values())
                    ),
                ),
                opacity=_opacity(),
                tooltip=[alt.Tooltip("label:N", title="severity"), "count"],
            )
            .add_params(point)
        )

    if kind == "incident_timeline":
        window = alt.selection_interval(name=SELECTION, encodings=["x"])
        return (
            alt.Chart(df, height=240)
            .mark_bar(width=9, cornerRadiusEnd=2)
            .encode(
                x=alt.X("week:T", title="week"),
                y=alt.Y("count:Q", title="incidents", stack=True),
                color=alt.Color(
                    "severity_label:N",
                    title="severity",
                    scale=alt.Scale(
                        domain=list(SEVERITY_COLORS), range=list(SEVERITY_COLORS.values())
                    ),
                ),
                order=alt.Order("severity:Q", sort="ascending"),
                tooltip=[
                    alt.Tooltip("week:T", title="week of"),
                    alt.Tooltip("severity_label:N", title="severity"),
                    "count",
                ],
            )
            .add_params(window)
        )

    if kind == "service_severity":
        point = alt.selection_point(name=SELECTION, fields=["service_id", "severity"], on="click")
        return (
            alt.Chart(df, height=max(160, 22 * df["service"].nunique() + 40))
            .mark_rect(cornerRadius=3, stroke="transparent", strokeWidth=2)
            .encode(
                x=alt.X(
                    "severity_label:N",
                    sort=list(SEVERITY_COLORS),
                    title=None,
                    axis=alt.Axis(labelAngle=0, orient="top"),
                ),
                y=alt.Y(
                    "service:N",
                    title=None,
                    sort=alt.EncodingSortField("count", "sum", "descending"),
                ),
                color=alt.Color("count:Q", title="incidents", scale=alt.Scale(range=SEQUENTIAL)),
                opacity=_opacity(),
                tooltip=["service", alt.Tooltip("severity_label:N", title="severity"), "count"],
            )
            .add_params(point)
        )

    if kind == "evidence_coverage":
        df["evidence_label"] = df["evidence"].map(EVIDENCE_LABELS)
        point = alt.selection_point(
            name=SELECTION, fields=["relation_type", "evidence"], on="click"
        )
        return (
            alt.Chart(df, height=max(140, 24 * df["relation_type"].nunique() + 50))
            .mark_bar(height={"band": 0.7}, stroke="white", strokeWidth=1)
            .encode(
                # Rows are already one per (relation_type, evidence); aggregating here would
                # drop the `_active` field that drives highlighting.
                y=alt.Y("relation_type:N", title=None, sort="-x"),
                x=alt.X("count:Q", title="edges", stack=True),
                color=alt.Color(
                    "evidence_label:N",
                    title="source",
                    scale=alt.Scale(
                        domain=[EVIDENCE_LABELS[k] for k in EVIDENCE_COLORS],
                        range=list(EVIDENCE_COLORS.values()),
                    ),
                ),
                opacity=_opacity(),
                tooltip=["relation_type", alt.Tooltip("evidence_label:N", title="source"), "count"],
            )
            .add_params(point)
        )
    return None


def selection_of(event: Any) -> Any:
    """Extract the selection payload from Streamlit's chart selection state."""
    try:
        return event["selection"][SELECTION]
    except (KeyError, TypeError):
        return None
